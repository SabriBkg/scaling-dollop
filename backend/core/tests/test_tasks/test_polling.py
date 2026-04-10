"""Tests for the hourly failure polling task."""
import pytest
from unittest.mock import patch, MagicMock
from datetime import timedelta

from cryptography.fernet import Fernet
from django.core.cache import cache
from django.utils import timezone

from core.models.subscriber import SubscriberFailure
from core.models.audit import AuditLog
from core.tasks.polling import poll_new_failures, poll_account_failures, POLL_LAST_RUN_KEY


@pytest.fixture(autouse=True)
def _fernet_key():
    key = Fernet.generate_key().decode()
    with patch.dict("os.environ", {"STRIPE_TOKEN_KEY": key}):
        from core.services import encryption
        encryption._cipher = None
        yield
        encryption._cipher = None


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


def _make_payment_intent(pi_id="pi_poll1", decline_code="expired_card", amount=2000, customer="cus_poll"):
    pi = MagicMock()
    pi.id = pi_id
    pi.status = "requires_payment_method"
    pi.amount = amount
    pi.customer = customer
    pi.created = 1700000000

    pi.last_payment_error = MagicMock()
    pi.last_payment_error.decline_code = decline_code

    charge = MagicMock()
    charge.billing_details.email = "poll@example.com"
    charge.payment_method_details.card.country = "GB"
    pi.charges.data = [charge]

    return pi


def _make_stripe_connection(account, access_token="sk_test_poll"):
    from core.models.account import StripeConnection
    conn = StripeConnection(account=account, stripe_user_id="acct_poll")
    conn.access_token = access_token
    conn.save()
    return conn


@pytest.mark.django_db
class TestPollNewFailures:
    def test_dispatches_subtasks(self, account):
        """poll_new_failures dispatches one subtask per account."""
        _make_stripe_connection(account)

        with patch("core.tasks.polling.poll_account_failures") as mock_subtask:
            result = poll_new_failures()

        assert result["accounts_dispatched"] == 1
        mock_subtask.delay.assert_called_once_with(account.id)


@pytest.mark.django_db
class TestPollAccountFailures:
    def test_detects_new_failures(self, account):
        """Polling creates SubscriberFailure records for new failures."""
        _make_stripe_connection(account)
        pi = _make_payment_intent()

        mock_list = MagicMock()
        mock_list.auto_paging_iter.return_value = [pi]

        with patch("core.tasks.polling.stripe.PaymentIntent.list", return_value=mock_list):
            result = poll_account_failures(account.id)

        assert result["new_failures"] == 1
        assert SubscriberFailure.objects.for_account(account.id).count() == 1

    def test_missed_cycle_alert(self, account):
        """If gap > 90 minutes since last poll, writes alert audit event."""
        _make_stripe_connection(account)
        cache_key = POLL_LAST_RUN_KEY.format(account_id=account.id)
        cache.set(cache_key, timezone.now() - timedelta(minutes=120))

        mock_list = MagicMock()
        mock_list.auto_paging_iter.return_value = []

        with patch("core.tasks.polling.stripe.PaymentIntent.list", return_value=mock_list):
            poll_account_failures(account.id)

        alert = AuditLog.objects.filter(action="polling_cycle_missed", account=account).first()
        assert alert is not None
        assert alert.outcome == "alert"
        assert alert.metadata["gap_minutes"] > 90

    def test_no_alert_within_threshold(self, account):
        """No alert if last poll was recent (within 90 min)."""
        _make_stripe_connection(account)
        cache_key = POLL_LAST_RUN_KEY.format(account_id=account.id)
        cache.set(cache_key, timezone.now() - timedelta(minutes=30))

        mock_list = MagicMock()
        mock_list.auto_paging_iter.return_value = []

        with patch("core.tasks.polling.stripe.PaymentIntent.list", return_value=mock_list):
            poll_account_failures(account.id)

        assert not AuditLog.objects.filter(action="polling_cycle_missed").exists()

    def test_rate_limit_retries(self, account):
        """Rate limit errors trigger Celery retry."""
        import stripe
        _make_stripe_connection(account)

        with patch("core.tasks.polling.stripe.PaymentIntent.list", side_effect=stripe.error.RateLimitError("rate limited")):
            with pytest.raises(stripe.error.RateLimitError):
                poll_account_failures(account.id)

    def test_audit_event_on_completion(self, account):
        """Successful poll writes completion audit event."""
        _make_stripe_connection(account)

        mock_list = MagicMock()
        mock_list.auto_paging_iter.return_value = []

        with patch("core.tasks.polling.stripe.PaymentIntent.list", return_value=mock_list):
            poll_account_failures(account.id)

        audit = AuditLog.objects.filter(action="polling_cycle_completed").first()
        assert audit is not None
        assert audit.outcome == "success"
        assert audit.account == account

    def test_updates_cache_after_poll(self, account):
        """After successful poll, cache key is updated with current time."""
        _make_stripe_connection(account)
        cache_key = POLL_LAST_RUN_KEY.format(account_id=account.id)

        mock_list = MagicMock()
        mock_list.auto_paging_iter.return_value = []

        with patch("core.tasks.polling.stripe.PaymentIntent.list", return_value=mock_list):
            poll_account_failures(account.id)

        assert cache.get(cache_key) is not None

    def test_skips_missing_connection(self, account):
        """Gracefully skips if StripeConnection no longer exists."""
        result = poll_account_failures(account.id)
        assert result["skipped"] is True
