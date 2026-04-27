"""Tests for the anonymous password reset endpoints (Story 4.5).

Two endpoints:
  - POST /api/v1/auth/password-reset/         — request reset link by email.
  - POST /api/v1/auth/password-reset/confirm/ — submit (uid, token, new password).

Both are anonymous; throttled per-email and per-IP. Email-enumeration defense
is the single most important behavioral contract — the request endpoint
ALWAYS returns a byte-identical generic 200 regardless of registration status.
"""
import logging

import pytest
from unittest.mock import patch

from django.contrib.auth.models import User
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from core.models.audit import AuditLog
from core.models.dead_letter import DeadLetterLog


REQUEST_URL = "/api/v1/auth/password-reset/"
CONFIRM_URL = "/api/v1/auth/password-reset/confirm/"
GENERIC_BODY = {
    "data": {"message": "If an account exists for that email, we've sent a reset link."}
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def user(db):
    """User with an auto-created Account (via post_save signal)."""
    return User.objects.create_user(
        username="founder@example.com",
        email="founder@example.com",
        password="OldPassword!2026",
    )


@pytest.fixture
def user_with_account(user):
    # Account is auto-created by core/signals.py on User post_save.
    return user


@pytest.fixture(autouse=True)
def _resend_configured(settings):
    settings.RESEND_API_KEY = "test_key"
    settings.SAFENET_FRONTEND_URL = "http://frontend.test"


@pytest.fixture(autouse=True)
def _default_resend_send():
    """Default Resend mock so confirm-flow tests (which trigger the
    password-changed notification email) don't make real HTTP calls.
    Tests that need a specific behavior decorate themselves with @patch
    on the same target — those decorators override this fixture for the
    test's duration.
    """
    with patch("core.services.email.resend.Emails.send", return_value={"id": "msg_default"}) as m:
        yield m


@pytest.fixture(autouse=True)
def _clear_throttle_cache():
    """Reset DRF throttle cache between tests so per-email/IP buckets don't bleed."""
    from django.core.cache import cache
    cache.clear()
    yield
    cache.clear()


def _build_confirm_payload(user, new_password="NewSecure!2026"):
    return {
        "uid": urlsafe_base64_encode(force_bytes(user.pk)),
        "token": PasswordResetTokenGenerator().make_token(user),
        "new_password": new_password,
        "new_password_confirm": new_password,
    }


# ---------------------------------------------------------------------------
# Request endpoint — POST /api/v1/auth/password-reset/
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestPasswordResetRequest:

    @patch("core.services.email.resend.Emails.send", return_value={"id": "msg_x"})
    def test_returns_200_for_registered_email(self, mock_resend, api_client, user_with_account):
        response = api_client.post(REQUEST_URL, {"email": "founder@example.com"}, format="json")
        assert response.status_code == 200
        assert response.json() == GENERIC_BODY

    @patch("core.services.email.resend.Emails.send", return_value={"id": "msg_x"})
    def test_returns_200_for_unregistered_email(self, mock_resend, api_client, db):
        response = api_client.post(REQUEST_URL, {"email": "ghost@nowhere.com"}, format="json")
        assert response.status_code == 200
        # byte-identical body — no enumeration via response shape
        assert response.json() == GENERIC_BODY

    @patch("core.services.email.resend.Emails.send", return_value={"id": "msg_x"})
    def test_returns_200_for_malformed_email(self, mock_resend, api_client, db):
        response = api_client.post(REQUEST_URL, {"email": "not-an-email"}, format="json")
        assert response.status_code == 200
        assert response.json() == GENERIC_BODY

    @patch("core.services.email.resend.Emails.send", return_value={"id": "msg_x"})
    def test_returns_200_for_missing_email(self, mock_resend, api_client, db):
        response = api_client.post(REQUEST_URL, {}, format="json")
        assert response.status_code == 200
        assert response.json() == GENERIC_BODY

    @patch("core.services.email.resend.Emails.send", return_value={"id": "msg_x"})
    def test_email_lookup_case_insensitive(self, mock_resend, api_client, user_with_account):
        response = api_client.post(REQUEST_URL, {"email": "FOUNDER@example.com"}, format="json")
        assert response.status_code == 200
        assert mock_resend.call_count == 1

    @patch("core.services.email.resend.Emails.send", return_value={"id": "msg_x"})
    def test_resend_called_for_registered_email(
        self, mock_resend, api_client, user_with_account
    ):
        api_client.post(REQUEST_URL, {"email": "founder@example.com"}, format="json")
        assert mock_resend.call_count == 1

    @patch("core.services.email.resend.Emails.send", return_value={"id": "msg_x"})
    def test_resend_not_called_for_unregistered_email(self, mock_resend, api_client, db):
        api_client.post(REQUEST_URL, {"email": "ghost@nowhere.com"}, format="json")
        assert mock_resend.call_count == 0

    @patch("core.services.email.resend.Emails.send", side_effect=RuntimeError("resend down"))
    def test_resend_failure_still_returns_200(
        self, mock_resend, api_client, user_with_account
    ):
        response = api_client.post(
            REQUEST_URL, {"email": "founder@example.com"}, format="json"
        )
        assert response.status_code == 200
        assert response.json() == GENERIC_BODY
        assert DeadLetterLog.objects.filter(task_name="password_reset_email").count() == 1

    @patch("core.services.email.resend.Emails.send", return_value={"id": "msg_x"})
    def test_audit_event_written_for_registered_email(
        self, mock_resend, api_client, user_with_account
    ):
        api_client.post(REQUEST_URL, {"email": "founder@example.com"}, format="json")
        rows = AuditLog.objects.filter(
            action="password_reset_requested",
            actor="client",
            account=user_with_account.account,
        )
        assert rows.count() == 1
        meta = rows.first().metadata
        assert meta["user_id"] == user_with_account.id
        # 16-char sha256 prefix; raw email NEVER in metadata
        assert len(meta["email_hash"]) == 16
        assert "founder@example.com" not in str(meta)

    @patch("core.services.email.resend.Emails.send", return_value={"id": "msg_x"})
    def test_audit_event_NOT_written_for_unregistered_email(
        self, mock_resend, api_client, db
    ):
        api_client.post(REQUEST_URL, {"email": "ghost@nowhere.com"}, format="json")
        assert AuditLog.objects.filter(action="password_reset_requested").count() == 0

    @patch("core.services.email.resend.Emails.send", side_effect=RuntimeError("resend down"))
    def test_audit_event_NOT_written_when_resend_fails(
        self, mock_resend, api_client, user_with_account
    ):
        api_client.post(REQUEST_URL, {"email": "founder@example.com"}, format="json")
        assert AuditLog.objects.filter(action="password_reset_requested").count() == 0

    @patch("core.services.email.resend.Emails.send", return_value={"id": "msg_x"})
    def test_email_url_uses_frontend_setting(
        self, mock_resend, api_client, user_with_account, settings
    ):
        settings.SAFENET_FRONTEND_URL = "https://frontend.test"
        api_client.post(REQUEST_URL, {"email": "founder@example.com"}, format="json")
        sent_html = mock_resend.call_args.args[0]["html"]
        assert "https://frontend.test/reset-password/" in sent_html

    @patch("core.services.email.resend.Emails.send", return_value={"id": "msg_x"})
    def test_email_subject_is_safenet_branded(
        self, mock_resend, api_client, user_with_account
    ):
        api_client.post(REQUEST_URL, {"email": "founder@example.com"}, format="json")
        subject = mock_resend.call_args.args[0]["subject"]
        assert subject == "Reset your SafeNet password"

    @patch("core.services.email.resend.Emails.send", return_value={"id": "msg_x"})
    def test_email_from_does_not_use_brand_prefix(
        self, mock_resend, api_client, user_with_account, settings
    ):
        settings.SAFENET_SENDING_DOMAIN = "payments.safenet.app"
        api_client.post(REQUEST_URL, {"email": "founder@example.com"}, format="json")
        from_field = mock_resend.call_args.args[0]["from"]
        assert "via SafeNet" not in from_field
        assert from_field == '"SafeNet" <noreply@payments.safenet.app>'

    @patch("core.services.email.resend.Emails.send", return_value={"id": "msg_x"})
    def test_raw_email_not_in_logs(self, mock_resend, api_client, db, caplog):
        caplog.set_level(logging.INFO, logger="core.views.password_reset")
        api_client.post(REQUEST_URL, {"email": "ghost@nowhere.com"}, format="json")
        # Use getMessage() to evaluate %-format args, per Story 4.4 caplog lesson.
        rendered = "\n".join(r.getMessage() for r in caplog.records)
        assert "ghost@nowhere.com" not in rendered
        assert "email_hash=" in rendered


# ---------------------------------------------------------------------------
# Throttle behavior — per-email on request, per-IP fallback
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestPasswordResetRequestThrottle:

    @patch("core.services.email.resend.Emails.send", return_value={"id": "msg_x"})
    def test_throttle_blocks_after_3_requests_per_email(
        self, mock_resend, api_client, user_with_account
    ):
        for _ in range(3):
            r = api_client.post(REQUEST_URL, {"email": "founder@example.com"}, format="json")
            assert r.status_code == 200
        r = api_client.post(REQUEST_URL, {"email": "founder@example.com"}, format="json")
        assert r.status_code == 429
        body = r.json()["error"]
        assert body["code"] == "RATE_LIMITED"
        assert body["message"] == "Too many password reset requests. Try again later."

    @patch("core.services.email.resend.Emails.send", return_value={"id": "msg_x"})
    def test_throttle_separates_buckets_per_email(
        self, mock_resend, api_client, db
    ):
        for _ in range(3):
            r = api_client.post(REQUEST_URL, {"email": "a@example.com"}, format="json")
            assert r.status_code == 200
        # Different email — independent bucket.
        r = api_client.post(REQUEST_URL, {"email": "b@example.com"}, format="json")
        assert r.status_code == 200

    @patch("core.services.email.resend.Emails.send", return_value={"id": "msg_x"})
    def test_throttle_falls_back_to_ip_for_blank_email(
        self, mock_resend, api_client, db
    ):
        for _ in range(3):
            r = api_client.post(REQUEST_URL, {}, format="json")
            assert r.status_code == 200
        r = api_client.post(REQUEST_URL, {}, format="json")
        assert r.status_code == 429

    def test_throttle_blank_email_uses_anon_ip_bucket_prefix(self, api_client, db):
        """Guard against future refactors that silently merge the anon-IP
        bucket with the email bucket — the cache key must carry the
        `_anon_<ip>` prefix when no email is provided."""
        from core.views.password_reset_throttles import PasswordResetRequestThrottle

        class _DummyView:
            pass

        class _DummyRequest:
            def __init__(self, data, ip):
                self.data = data
                self.META = {"REMOTE_ADDR": ip}

            def get_full_path(self):
                return REQUEST_URL

        throttle = PasswordResetRequestThrottle()
        # Avoid DRF's get_ident proxy logic — feed it directly via the throttle.
        key = throttle.get_cache_key(
            type("R", (), {"data": {}, "META": {"REMOTE_ADDR": "1.2.3.4"}})(),
            None,
        )
        assert key is not None
        assert key.startswith("throttle_password_reset_anon_")

    @patch("core.services.email.resend.Emails.send", return_value={"id": "msg_x"})
    def test_throttle_uses_canonical_email_keying(
        self, mock_resend, api_client, db
    ):
        # Mixed casing/whitespace should canonicalize to the same bucket.
        api_client.post(REQUEST_URL, {"email": "  FOO@bar.com  "}, format="json")
        api_client.post(REQUEST_URL, {"email": "foo@bar.com"}, format="json")
        api_client.post(REQUEST_URL, {"email": "Foo@Bar.com"}, format="json")
        r = api_client.post(REQUEST_URL, {"email": "foo@bar.com"}, format="json")
        assert r.status_code == 429


# ---------------------------------------------------------------------------
# Confirm endpoint — POST /api/v1/auth/password-reset/confirm/
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestPasswordResetConfirm:

    def test_valid_token_updates_password(self, api_client, user_with_account):
        payload = _build_confirm_payload(user_with_account)
        response = api_client.post(CONFIRM_URL, payload, format="json")
        assert response.status_code == 200
        user_with_account.refresh_from_db()
        assert user_with_account.check_password("NewSecure!2026")

    def test_old_password_no_longer_works(self, api_client, user_with_account):
        payload = _build_confirm_payload(user_with_account)
        api_client.post(CONFIRM_URL, payload, format="json")
        user_with_account.refresh_from_db()
        assert not user_with_account.check_password("OldPassword!2026")

    def test_password_argon2_hashed(self, api_client, user_with_account):
        payload = _build_confirm_payload(user_with_account)
        api_client.post(CONFIRM_URL, payload, format="json")
        user_with_account.refresh_from_db()
        assert user_with_account.password.startswith("argon2")

    def test_token_invalidated_after_use(self, api_client, user_with_account):
        # First reset succeeds.
        payload = _build_confirm_payload(user_with_account, new_password="First!2026Pass")
        first = api_client.post(CONFIRM_URL, payload, format="json")
        assert first.status_code == 200

        # Same (uid, token) re-posted with a different new password — must fail
        # (PasswordResetTokenGenerator hash includes user.password, which just
        # changed, so check_token now returns False).
        replay = {**payload, "new_password": "Second!2026Pass", "new_password_confirm": "Second!2026Pass"}
        response = api_client.post(CONFIRM_URL, replay, format="json")
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "INVALID_RESET_LINK"

    def test_invalid_uid_returns_400(self, api_client, user_with_account):
        payload = _build_confirm_payload(user_with_account)
        payload["uid"] = "garbage!!!"
        response = api_client.post(CONFIRM_URL, payload, format="json")
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "INVALID_RESET_LINK"

    def test_unknown_user_returns_400(self, api_client, user_with_account):
        payload = _build_confirm_payload(user_with_account)
        payload["uid"] = urlsafe_base64_encode(force_bytes(99999))
        response = api_client.post(CONFIRM_URL, payload, format="json")
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "INVALID_RESET_LINK"

    def test_tampered_token_returns_400(self, api_client, user_with_account):
        payload = _build_confirm_payload(user_with_account)
        # Flip the last char to a different valid token alphabet char.
        original = payload["token"]
        last = original[-1]
        replacement = "a" if last != "a" else "b"
        payload["token"] = original[:-1] + replacement
        response = api_client.post(CONFIRM_URL, payload, format="json")
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "INVALID_RESET_LINK"

    def test_response_is_byte_identical_for_bad_uid_vs_check_token_failed(
        self, api_client, user_with_account
    ):
        # Branch 1: bad uid.
        bad_uid_payload = _build_confirm_payload(user_with_account)
        bad_uid_payload["uid"] = "garbage"
        bad_uid_resp = api_client.post(CONFIRM_URL, bad_uid_payload, format="json")

        # Branch 2: valid uid, tampered token.
        bad_token_payload = _build_confirm_payload(user_with_account)
        bad_token_payload["token"] = bad_token_payload["token"][:-1] + "x"
        bad_token_resp = api_client.post(CONFIRM_URL, bad_token_payload, format="json")

        assert bad_uid_resp.status_code == bad_token_resp.status_code == 400
        assert bad_uid_resp.json() == bad_token_resp.json()

    def test_password_mismatch_returns_400_validation(self, api_client, user_with_account):
        payload = _build_confirm_payload(user_with_account)
        payload["new_password_confirm"] = "DifferentPass!2026"
        response = api_client.post(CONFIRM_URL, payload, format="json")
        assert response.status_code == 400
        body = response.json()["error"]
        assert body["code"] == "VALIDATION_ERROR"
        assert body["field"] == "new_password_confirm"

    def test_weak_password_rejected(self, api_client, user_with_account):
        payload = _build_confirm_payload(user_with_account, new_password="password")
        response = api_client.post(CONFIRM_URL, payload, format="json")
        assert response.status_code == 400
        body = response.json()["error"]
        assert body["code"] == "VALIDATION_ERROR"
        assert body["field"] == "new_password"

    def test_password_too_similar_to_email_rejected(self, api_client, user_with_account):
        # UserAttributeSimilarityValidator compares against username/email/etc.
        payload = _build_confirm_payload(
            user_with_account, new_password="founder@example.com"
        )
        response = api_client.post(CONFIRM_URL, payload, format="json")
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"

    def test_audit_password_reset_completed_written(self, api_client, user_with_account):
        payload = _build_confirm_payload(user_with_account)
        api_client.post(CONFIRM_URL, payload, format="json")
        rows = AuditLog.objects.filter(
            action="password_reset_completed",
            actor="client",
            account=user_with_account.account,
        )
        assert rows.count() == 1
        meta = rows.first().metadata
        assert meta["user_id"] == user_with_account.id
        # No raw password / token in metadata
        assert "NewSecure" not in str(meta)
        assert payload["token"] not in str(meta)

    def test_password_reset_timeout_setting_is_one_hour(self):
        """Structural guard for the 1-hour expiry contract (epic line 911).

        A timing-based "token expires after 61 minutes" test would require
        freezegun, which is not installed. Asserting the setting itself
        guards the contract; PasswordResetTokenGenerator.check_token()
        consumes settings.PASSWORD_RESET_TIMEOUT directly.
        """
        from django.conf import settings as dj_settings
        assert dj_settings.PASSWORD_RESET_TIMEOUT == 3600

    def test_unknown_user_logs_user_not_found_reason(self, api_client, user_with_account, caplog):
        caplog.set_level(logging.WARNING, logger="core.views.password_reset")
        payload = _build_confirm_payload(user_with_account)
        payload["uid"] = urlsafe_base64_encode(force_bytes(99999))
        api_client.post(CONFIRM_URL, payload, format="json")
        rendered = "\n".join(r.getMessage() for r in caplog.records)
        assert "reason=user_not_found" in rendered
        assert "reason=bad_uid" not in rendered

    def test_bad_uid_logs_bad_uid_reason(self, api_client, user_with_account, caplog):
        caplog.set_level(logging.WARNING, logger="core.views.password_reset")
        payload = _build_confirm_payload(user_with_account)
        payload["uid"] = "garbage!!!"
        api_client.post(CONFIRM_URL, payload, format="json")
        rendered = "\n".join(r.getMessage() for r in caplog.records)
        assert "reason=bad_uid" in rendered
        assert "reason=user_not_found" not in rendered

    def test_raw_token_not_in_logs(self, api_client, user_with_account, caplog):
        caplog.set_level(logging.WARNING, logger="core.views.password_reset")
        payload = _build_confirm_payload(user_with_account)
        original_token = payload["token"]
        payload["token"] = original_token[:-1] + ("a" if original_token[-1] != "a" else "b")
        api_client.post(CONFIRM_URL, payload, format="json")
        rendered = "\n".join(r.getMessage() for r in caplog.records)
        assert payload["token"] not in rendered
        assert "reason=check_token_failed" in rendered

    def test_throttle_5_per_min_on_confirm(self, api_client, db):
        # 5 garbage POSTs each return 400; 6th hits the IP-keyed auth-scope throttle.
        for _ in range(5):
            r = api_client.post(
                CONFIRM_URL,
                {"uid": "garbage", "token": "x", "new_password": "y", "new_password_confirm": "y"},
                format="json",
            )
            assert r.status_code == 400
        r = api_client.post(
            CONFIRM_URL,
            {"uid": "garbage", "token": "x", "new_password": "y", "new_password_confirm": "y"},
            format="json",
        )
        assert r.status_code == 429
        body = r.json()["error"]
        assert body["code"] == "RATE_LIMITED"
        assert body["message"] == "Too many password reset requests. Try again later."
