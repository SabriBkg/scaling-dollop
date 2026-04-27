"""End-to-end opt-out flow (Story 4.4 Task 7).

Single integration test that exercises every layer:
signing → email rendering → URL extraction → public view → opt-out persistence
→ Gate 4 suppression of a subsequent send.
"""
import re

import pytest
from cryptography.fernet import Fernet
from unittest.mock import patch
from django.utils import timezone

from core.models.account import StripeConnection, TIER_MID
from core.models.notification import NotificationLog, NotificationOptOut
from core.models.subscriber import Subscriber, SubscriberFailure
from core.services.email import send_notification_email
from core.services.optout_token import build_optout_url, decode_optout_token
from core.tasks.notifications import send_failure_notification


@pytest.fixture(autouse=True)
def _fernet_key():
    key = Fernet.generate_key().decode()
    with patch.dict("os.environ", {"STRIPE_TOKEN_KEY": key}):
        from core.services import encryption
        encryption._cipher = None
        yield
        encryption._cipher = None


@pytest.fixture
def mid_account(account):
    account.tier = TIER_MID
    account.dpa_accepted_at = timezone.now()
    account.engine_mode = "autopilot"
    account.company_name = "TestCo"
    account.save()
    conn = StripeConnection(account=account, stripe_user_id="acct_test")
    conn.access_token = "sk_test"
    conn.save()
    return account


@pytest.mark.django_db
class TestOptoutEndToEnd:
    @patch("core.services.email.resend.Emails.send")
    def test_full_optout_flow(self, mock_resend, client, mid_account, settings):
        settings.RESEND_API_KEY = "test_key"
        settings.SAFENET_BASE_URL = "http://testserver"
        mock_resend.return_value = {"id": "msg_e2e"}

        # Set up subscriber + 2 failures (we'll send the first, opt out, then
        # try the second — second must be suppressed by Gate 4).
        mid_account.customer_update_url = "https://example.com/billing"
        mid_account.save()
        sub = Subscriber.objects.create(
            account=mid_account,
            stripe_customer_id="cus_e2e",
            email="sub@x.com",
        )
        f1 = SubscriberFailure.objects.create(
            account=mid_account,
            subscriber=sub,
            payment_intent_id="pi_e2e_1",
            decline_code="card_expired",
            amount_cents=2000,
            failure_created_at=timezone.now(),
            classified_action="retry_notify",
        )
        f2 = SubscriberFailure.objects.create(
            account=mid_account,
            subscriber=sub,
            payment_intent_id="pi_e2e_2",
            decline_code="insufficient_funds",
            amount_cents=2500,
            failure_created_at=timezone.now(),
            classified_action="retry_notify",
        )

        # Step 1: helper renders the email — capture the HTML.
        send_notification_email(sub, f1, mid_account)
        sent_html = mock_resend.call_args[0][0]["html"]
        # Assert the URL appears verbatim — protects against silent escape /
        # canonicalization regressions that would still satisfy a regex match.
        expected_url = build_optout_url("sub@x.com", mid_account.id)
        assert expected_url in sent_html

        # Step 2: extract the token and verify the payload it carries.
        match = re.search(r"/optout/([^/\"]+)/", sent_html)
        assert match, f"No /optout/ URL found in HTML: {sent_html[:300]}"
        token = match.group(1)
        decoded = decode_optout_token(token)
        assert decoded == {"email": "sub@x.com", "account_id": mid_account.id}

        # Step 3: hit the public confirm GET — no row should be created.
        response = client.get(f"/optout/{token}/")
        assert response.status_code == 200
        assert b"Confirm" in response.content
        assert NotificationOptOut.objects.count() == 0

        # Step 4: POST to commit. Row + audit appear.
        response = client.post(f"/optout/{token}/")
        assert response.status_code == 200
        assert NotificationOptOut.objects.filter(
            account=mid_account, subscriber_email="sub@x.com",
        ).exists()

        # Step 5: a SECOND failure on the same subscriber must be suppressed
        # by Gate 4 (no further Resend send).
        mock_resend.reset_mock()
        send_failure_notification(f2.id)
        mock_resend.assert_not_called()
        suppressed = NotificationLog.objects.get(
            failure=f2, status="suppressed",
        )
        assert suppressed.metadata["reason"] == "opt_out"
