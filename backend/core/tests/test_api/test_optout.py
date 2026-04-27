"""Public, unauthenticated opt-out view (Story 4.4 Task 5).

The endpoint returns HTML, not JSON — we use Django's `Client` here, NOT DRF's
`APIClient`. Sits at the project URLConf level (`/optout/<token>/`), outside
the JWT-protected `/api/v1/` surface.
"""
import re

import pytest
from cryptography.fernet import Fernet
from unittest.mock import patch

from django.utils import timezone

from core.models.account import StripeConnection, TIER_MID
from core.models.audit import AuditLog
from core.models.notification import NotificationOptOut
from core.models.subscriber import Subscriber
from core.services.optout_token import build_optout_token


OPTOUT_URL = "/optout/{token}/"


@pytest.fixture(autouse=True)
def _fernet_key():
    """Stub the Fernet key so encryption-touching code paths don't error
    even though the optout view itself never decrypts anything."""
    key = Fernet.generate_key().decode()
    with patch.dict("os.environ", {"STRIPE_TOKEN_KEY": key}):
        from core.services import encryption
        encryption._cipher = None
        yield
        encryption._cipher = None


@pytest.fixture
def mid_account(account):
    """Mid-tier account with company_name (mirrors the test_notifications.py pattern)."""
    account.tier = TIER_MID
    account.dpa_accepted_at = timezone.now()
    account.engine_mode = "autopilot"
    account.company_name = "TestCo"
    account.save()

    conn = StripeConnection(account=account, stripe_user_id="acct_test")
    conn.access_token = "sk_test"
    conn.save()

    return account


def _url_for(email: str, account_id: int) -> str:
    return OPTOUT_URL.format(token=build_optout_token(email, account_id))


@pytest.mark.django_db
class TestOptoutGetConfirm:
    def test_get_returns_confirm_page_for_valid_token(self, client, mid_account):
        url = _url_for("sub@x.com", mid_account.id)
        response = client.get(url)
        assert response.status_code == 200
        assert b"Confirm" in response.content
        assert b'<form method="POST"' in response.content
        assert b"TestCo" in response.content

    def test_get_does_not_create_optout_row(self, client, mid_account):
        """Email scanners (Gmail/Outlook) prefetch links; GET must be read-only."""
        url = _url_for("sub@x.com", mid_account.id)
        client.get(url)
        assert NotificationOptOut.objects.count() == 0

    def test_get_does_not_write_audit(self, client, mid_account):
        url = _url_for("sub@x.com", mid_account.id)
        client.get(url)
        assert AuditLog.objects.filter(action="notification_opted_out").count() == 0


@pytest.mark.django_db
class TestOptoutPostCommit:
    def test_post_creates_optout_row(self, client, mid_account):
        url = _url_for("sub@x.com", mid_account.id)
        response = client.post(url)
        assert response.status_code == 200
        assert NotificationOptOut.objects.filter(
            account=mid_account, subscriber_email="sub@x.com",
        ).exists()

    def test_post_writes_audit_event(self, client, mid_account):
        url = _url_for("sub@x.com", mid_account.id)
        client.post(url)
        rows = AuditLog.objects.filter(
            action="notification_opted_out",
            actor="subscriber",
            account=mid_account,
        )
        assert rows.count() == 1
        audit = rows.first()
        assert audit.outcome == "success"
        assert audit.metadata["subscriber_email"] == "sub@x.com"
        assert audit.metadata["account_id"] == mid_account.id
        assert audit.metadata["company_name"] == "TestCo"

    def test_post_idempotent_when_row_already_exists(self, client, mid_account):
        # Pre-create the row directly (not via the view) — emulate a replay.
        NotificationOptOut.objects.create(
            account=mid_account, subscriber_email="sub@x.com",
        )
        url = _url_for("sub@x.com", mid_account.id)
        response = client.post(url)
        assert response.status_code == 200
        assert NotificationOptOut.objects.count() == 1
        # The pre-existing row was created directly; the view must NOT write a
        # second audit row for the duplicate POST.
        assert AuditLog.objects.filter(action="notification_opted_out").count() == 0

    def test_post_renders_success_page(self, client, mid_account):
        url = _url_for("sub@x.com", mid_account.id)
        response = client.post(url)
        assert b"unsubscribed" in response.content.lower()
        assert b"TestCo" in response.content

    def test_post_canonicalizes_email_at_sign_time(self, client, mid_account):
        # Token signed with mixed case + whitespace; the helper canonicalizes.
        url = _url_for("  Sub@X.COM  ", mid_account.id)
        client.post(url)
        row = NotificationOptOut.objects.get(account=mid_account)
        assert row.subscriber_email == "sub@x.com"

    def test_gate4_iexact_lookup_finds_row_across_email_casing(self, client, mid_account):
        """Cross-case lookup: a token signed with one casing must produce a row
        that satisfies the gate-4 ``__iexact`` filter keyed on a *different*
        casing — locks in the canonicalization contract end-to-end."""
        url = _url_for("Sub@X.COM", mid_account.id)
        client.post(url)
        # Gate 4's actual filter (notifications.py:64-67) — must find the row.
        assert NotificationOptOut.objects.filter(
            subscriber_email__iexact="SUB@x.com",
            account=mid_account,
        ).exists(), "gate-4 __iexact lookup must find the canonicalized row"


@pytest.mark.django_db
class TestOptoutInvalidToken:
    def test_invalid_token_returns_generic_message(self, client, mid_account):
        url = OPTOUT_URL.format(token="garbage")
        response = client.get(url)
        assert response.status_code == 200
        assert b"no longer valid" in response.content
        assert NotificationOptOut.objects.count() == 0
        assert AuditLog.objects.count() == 0

    def test_invalid_token_does_not_leak_account_existence(self, client, mid_account):
        # account_id=99999 does not exist — response must be the same generic page.
        url = _url_for("sub@x.com", 99999)
        response = client.get(url)
        assert response.status_code == 200
        assert b"no longer valid" in response.content

        # Byte-identical to a tampered-token response — the "valid signature +
        # missing account" branch must not be distinguishable from the
        # "bad signature" branch via response content.
        tampered = client.get(OPTOUT_URL.format(token="garbage"))
        assert response.content == tampered.content

    def test_get_tampered_token_returns_generic(self, client, mid_account):
        token = build_optout_token("sub@x.com", mid_account.id)
        idx = len(token) // 2
        flipped = "A" if token[idx] != "A" else "B"
        bad = token[:idx] + flipped + token[idx + 1:]
        response = client.get(OPTOUT_URL.format(token=bad))
        assert response.status_code == 200
        assert b"no longer valid" in response.content
        assert NotificationOptOut.objects.count() == 0


@pytest.mark.django_db
class TestOptoutAuditSubscriberLookup:
    def test_post_with_no_subscriber_row_still_audits(self, client, mid_account):
        """A subscriber who never had a Subscriber row can still opt out."""
        url = _url_for("ghost@x.com", mid_account.id)
        client.post(url)
        audit = AuditLog.objects.get(action="notification_opted_out")
        assert audit.subscriber_id is None
        assert audit.metadata["subscriber_email"] == "ghost@x.com"

    def test_post_finds_subscriber_for_audit(self, client, mid_account):
        sub = Subscriber.objects.create(
            account=mid_account,
            stripe_customer_id="cus_for_audit",
            email="sub@x.com",
        )
        url = _url_for("sub@x.com", mid_account.id)
        client.post(url)
        audit = AuditLog.objects.get(action="notification_opted_out")
        assert audit.subscriber_id == str(sub.id)


@pytest.mark.django_db
class TestOptoutHttpSemantics:
    def test_csrf_exempt_post_works_without_cookie(self, client, mid_account):
        # Default Django Client doesn't send CSRF tokens; if the view weren't
        # @csrf_exempt this would 403.
        url = _url_for("sub@x.com", mid_account.id)
        response = client.post(url)
        assert response.status_code == 200

    def test_disallowed_method_returns_405(self, client, mid_account):
        url = _url_for("sub@x.com", mid_account.id)
        response = client.put(url)
        assert response.status_code == 405

    def test_response_includes_robots_meta_on_confirm(self, client, mid_account):
        url = _url_for("sub@x.com", mid_account.id)
        response = client.get(url)
        assert b"noindex,nofollow" in response.content

    def test_response_includes_robots_meta_on_success(self, client, mid_account):
        url = _url_for("sub@x.com", mid_account.id)
        response = client.post(url)
        assert b"noindex,nofollow" in response.content


@pytest.mark.django_db
class TestOptoutXssSafety:
    def test_company_name_escaped_in_confirm_page(self, client, mid_account):
        mid_account.company_name = "<script>alert(1)</script>"
        mid_account.save()
        url = _url_for("sub@x.com", mid_account.id)
        response = client.get(url)
        body = response.content
        assert b"<script>alert(1)</script>" not in body
        assert b"&lt;script&gt;" in body

    def test_company_name_escaped_in_success_page(self, client, mid_account):
        mid_account.company_name = "<script>alert(1)</script>"
        mid_account.save()
        url = _url_for("sub@x.com", mid_account.id)
        response = client.post(url)
        body = response.content
        assert b"<script>alert(1)</script>" not in body
        assert b"&lt;script&gt;" in body


@pytest.mark.django_db
class TestOptoutObservability:
    def test_invalid_token_logs_warning_without_token_value(self, client, caplog):
        import logging
        with caplog.at_level(logging.WARNING, logger="core.views.optout"):
            client.get(OPTOUT_URL.format(token="garbage-token-value-xyz"))
        # Filter to records emitted by THIS view's logger — guards against
        # unrelated loggers happening to contain the literal "INVALID_TOKEN".
        view_records = [r for r in caplog.records if r.name == "core.views.optout"]
        assert any("INVALID_TOKEN" in r.getMessage() for r in view_records), (
            "view must log INVALID_TOKEN on bad signature"
        )
        # Raw token must NEVER appear — check the formatted message AND the
        # unformatted args tuple (a future patch adding `token=%s` would slip
        # past a `r.message`-only assertion).
        for r in view_records:
            assert "garbage-token-value-xyz" not in r.getMessage()
            assert "garbage-token-value-xyz" not in str(r.args or ())
