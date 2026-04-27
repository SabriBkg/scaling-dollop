"""End-to-end password reset flow (Story 4.5 Task 8).

Single integration test that exercises every layer:
request endpoint → email rendering → URL extraction from HTML →
confirm endpoint → password actually changes → token is single-use →
both audit events present.
"""
import re

import pytest
from unittest.mock import patch

from django.contrib.auth.models import User

from core.models.audit import AuditLog


@pytest.fixture
def user_with_account(db):
    return User.objects.create_user(
        username="founder@example.com",
        email="founder@example.com",
        password="OldPassword!2026",
    )


@pytest.fixture(autouse=True)
def _resend_configured(settings):
    settings.RESEND_API_KEY = "test_key"
    settings.SAFENET_FRONTEND_URL = "http://frontend.test"


@pytest.fixture(autouse=True)
def _clear_throttle_cache():
    from django.core.cache import cache
    cache.clear()
    yield
    cache.clear()


@pytest.mark.django_db
@patch("core.services.email.resend.Emails.send", return_value={"id": "msg_e2e"})
def test_full_password_reset_flow(mock_resend, api_client, user_with_account):
    # Step 1: request — generic 200, email sent.
    response = api_client.post(
        "/api/v1/auth/password-reset/",
        {"email": "founder@example.com"},
        format="json",
    )
    assert response.status_code == 200
    assert response.json() == {
        "data": {"message": "If an account exists for that email, we've sent a reset link."}
    }

    # Step 2: extract the reset URL from the rendered HTML.
    sent_html = mock_resend.call_args[0][0]["html"]
    match = re.search(
        r"http://frontend\.test/reset-password/([^/]+)/([^\"]+)",
        sent_html,
    )
    assert match, sent_html[:300]
    uid, token = match.group(1), match.group(2)

    # Step 3: confirm — set new password.
    response = api_client.post(
        "/api/v1/auth/password-reset/confirm/",
        {
            "uid": uid,
            "token": token,
            "new_password": "NewSecure!2026",
            "new_password_confirm": "NewSecure!2026",
        },
        format="json",
    )
    assert response.status_code == 200
    assert response.json() == {
        "data": {"message": "Password updated. You can now sign in."}
    }

    # Step 4: verify password actually changed.
    user_with_account.refresh_from_db()
    assert user_with_account.check_password("NewSecure!2026")
    assert not user_with_account.check_password("OldPassword!2026")

    # Step 5: token is now single-use — re-confirming fails.
    response = api_client.post(
        "/api/v1/auth/password-reset/confirm/",
        {
            "uid": uid,
            "token": token,
            "new_password": "AnotherPassword!2026",
            "new_password_confirm": "AnotherPassword!2026",
        },
        format="json",
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_RESET_LINK"

    # Step 6: both audit events present.
    assert AuditLog.objects.filter(action="password_reset_requested").count() == 1
    assert AuditLog.objects.filter(action="password_reset_completed").count() == 1
