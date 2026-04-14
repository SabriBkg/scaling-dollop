"""Tests for the retroactive 90-day failure scanner task."""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone as dt_tz

from cryptography.fernet import Fernet

from core.models.subscriber import Subscriber, SubscriberFailure
from core.models.audit import AuditLog
from core.tasks.scanner import scan_retroactive_failures


@pytest.fixture(autouse=True)
def _fernet_key():
    key = Fernet.generate_key().decode()
    with patch.dict("os.environ", {"STRIPE_TOKEN_KEY": key}):
        from core.services import encryption
        encryption._cipher = None
        yield
        encryption._cipher = None


def _make_payment_intent(
    pi_id="pi_test1",
    status="requires_payment_method",
    decline_code="insufficient_funds",
    amount=5000,
    customer="cus_abc",
    email="sub@example.com",
    country="US",
    created=1700000000,
):
    """Build a mock Stripe PaymentIntent matching the API shape."""
    pi = MagicMock()
    pi.id = pi_id
    pi.status = status
    pi.amount = amount
    pi.customer = customer
    pi.created = created

    pi.last_payment_error = MagicMock()
    pi.last_payment_error.decline_code = decline_code

    charge = MagicMock()
    charge.billing_details.email = email
    charge.payment_method_details.card.country = country
    charge.payment_method_details.card.fingerprint = "fp_test_scanner"
    pi.charges.data = [charge]

    return pi


def _make_stripe_connection(account, access_token="sk_test_xxx"):
    from core.models.account import StripeConnection
    conn = StripeConnection(account=account, stripe_user_id="acct_test")
    conn.access_token = access_token
    conn.save()
    return conn


@pytest.mark.django_db
class TestScanRetroactiveFailures:
    def test_creates_subscriber_and_failure(self, account):
        """Scan creates Subscriber + SubscriberFailure from Stripe data."""
        _make_stripe_connection(account)
        pi = _make_payment_intent()

        mock_list = MagicMock()
        mock_list.auto_paging_iter.return_value = [pi]

        with patch("core.tasks.scanner.stripe.PaymentIntent.list", return_value=mock_list):
            result = scan_retroactive_failures(account.id)

        assert result == {"processed": 1, "created": 1}
        assert Subscriber.objects.for_account(account.id).count() == 1
        assert SubscriberFailure.objects.for_account(account.id).count() == 1

        failure = SubscriberFailure.objects.get(payment_intent_id="pi_test1")
        assert failure.decline_code == "insufficient_funds"
        assert failure.amount_cents == 5000
        assert failure.classified_action == "retry_notify"
        assert failure.payment_method_country == "US"

    def test_idempotent_rerun(self, account):
        """Re-running scan does not duplicate records."""
        _make_stripe_connection(account)
        pi = _make_payment_intent()

        mock_list = MagicMock()
        mock_list.auto_paging_iter.return_value = [pi]

        with patch("core.tasks.scanner.stripe.PaymentIntent.list", return_value=mock_list):
            scan_retroactive_failures(account.id)
            result = scan_retroactive_failures(account.id)

        assert result == {"processed": 1, "created": 0}
        assert SubscriberFailure.objects.for_account(account.id).count() == 1

    def test_rate_limit_retries(self, account):
        """Rate limit errors trigger Celery retry with exponential backoff."""
        import stripe
        _make_stripe_connection(account)

        with patch("core.tasks.scanner.stripe.PaymentIntent.list", side_effect=stripe.error.RateLimitError("rate limited")):
            # self.retry() re-raises the original exception when called outside a worker
            with pytest.raises(stripe.error.RateLimitError):
                scan_retroactive_failures(account.id)

    def test_audit_event_on_completion(self, account):
        """Successful scan writes an audit event."""
        _make_stripe_connection(account)

        mock_list = MagicMock()
        mock_list.auto_paging_iter.return_value = []

        with patch("core.tasks.scanner.stripe.PaymentIntent.list", return_value=mock_list):
            scan_retroactive_failures(account.id)

        audit = AuditLog.objects.filter(action="retroactive_scan_completed", account=account).first()
        assert audit is not None
        assert audit.outcome == "success"

    def test_audit_event_on_failure(self, account):
        """Failed scan writes an audit event with error details."""
        _make_stripe_connection(account)

        with patch("core.tasks.scanner.stripe.PaymentIntent.list", side_effect=ValueError("test error")):
            with pytest.raises(ValueError):
                scan_retroactive_failures(account.id)

        audit = AuditLog.objects.filter(action="retroactive_scan_failed", account=account).first()
        assert audit is not None
        assert audit.outcome == "failed"
        assert "test error" in audit.metadata["error"]

    def test_skips_non_failed_intents(self, account):
        """Only processes intents with status 'requires_payment_method'."""
        _make_stripe_connection(account)

        pi_failed = _make_payment_intent(pi_id="pi_failed", status="requires_payment_method")
        pi_success = _make_payment_intent(pi_id="pi_success", status="succeeded")

        mock_list = MagicMock()
        mock_list.auto_paging_iter.return_value = [pi_failed, pi_success]

        with patch("core.tasks.scanner.stripe.PaymentIntent.list", return_value=mock_list):
            result = scan_retroactive_failures(account.id)

        assert result == {"processed": 1, "created": 1}

    def test_default_decline_code(self, account):
        """None decline code falls through to _default rule."""
        _make_stripe_connection(account)
        pi = _make_payment_intent(decline_code=None)
        pi.last_payment_error.decline_code = None

        mock_list = MagicMock()
        mock_list.auto_paging_iter.return_value = [pi]

        with patch("core.tasks.scanner.stripe.PaymentIntent.list", return_value=mock_list):
            scan_retroactive_failures(account.id)

        failure = SubscriberFailure.objects.get(payment_intent_id="pi_test1")
        assert failure.decline_code == "_default"
        assert failure.classified_action == "retry_notify"  # _default action
