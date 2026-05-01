"""Tests for the daily failure polling task."""
import pytest
from unittest.mock import patch, MagicMock
from datetime import timedelta

from cryptography.fernet import Fernet
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from core.models.subscriber import Subscriber, SubscriberFailure
from core.models.audit import AuditLog
from core.tasks.polling import (
    poll_new_failures,
    poll_account_failures,
    POLL_LAST_RUN_KEY,
    _check_payment_recoveries,
)


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


@pytest.fixture(autouse=True)
def _mock_notification_dispatch():
    """Prevent notification task dispatch from trying to connect to Redis."""
    with patch("core.tasks.notifications.send_failure_notification.delay") as mock_notify:
        yield mock_notify


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
    charge.payment_method_details.card.fingerprint = "fp_test_polling"
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

        with patch("core.tasks.polling.stripe.PaymentIntent.list", side_effect=stripe.RateLimitError("rate limited")):
            with pytest.raises(stripe.RateLimitError):
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

    def test_free_tier_skips_when_not_due(self, account):
        """Free-tier accounts skip polling when last poll was recent."""
        from core.models.account import TIER_FREE
        account.tier = TIER_FREE
        account.save()
        _make_stripe_connection(account)

        # Set last poll to 1 day ago — far less than 15-day Free interval
        cache_key = POLL_LAST_RUN_KEY.format(account_id=account.id)
        cache.set(cache_key, timezone.now() - timedelta(days=1))

        result = poll_account_failures(account.id)
        assert result["skipped_free_tier"] is True

    def test_free_tier_polls_when_due(self, account):
        """Free-tier accounts poll when enough time has passed."""
        from core.models.account import TIER_FREE
        account.tier = TIER_FREE
        account.save()
        _make_stripe_connection(account)

        # Set last poll to 16 days ago — past the 15-day Free interval
        cache_key = POLL_LAST_RUN_KEY.format(account_id=account.id)
        cache.set(cache_key, timezone.now() - timedelta(days=16))

        mock_list = MagicMock()
        mock_list.auto_paging_iter.return_value = []

        with patch("core.tasks.polling.stripe.PaymentIntent.list", return_value=mock_list):
            result = poll_account_failures(account.id)

        assert "skipped_free_tier" not in result
        assert result["new_failures"] == 0

    def test_free_tier_polls_on_first_run(self, account):
        """Free-tier accounts poll if no previous poll exists (first run)."""
        from core.models.account import TIER_FREE
        account.tier = TIER_FREE
        account.save()
        _make_stripe_connection(account)

        mock_list = MagicMock()
        mock_list.auto_paging_iter.return_value = []

        with patch("core.tasks.polling.stripe.PaymentIntent.list", return_value=mock_list):
            result = poll_account_failures(account.id)

        assert "skipped_free_tier" not in result


# Story 3.4 v1 — status detection driven by daily polling

@pytest.fixture
def mid_v1_account(account):
    """Mid-tier with DPA, engine_mode=None — the v1 default."""
    from core.models.account import TIER_MID
    account.tier = TIER_MID
    account.dpa_accepted_at = timezone.now()
    account.engine_mode = None
    account.save()
    return account


def _make_subscription_mock(status="active", cancel_at_period_end=False, sub_id="sub_x"):
    sub = MagicMock()
    sub.id = sub_id
    sub.status = status
    sub.cancel_at_period_end = cancel_at_period_end
    return sub


@pytest.mark.django_db
class TestV1StatusDetection:
    """Story 3.4 v1 — cancellation polling ungated; payment recovery detected."""

    def test_cancellation_detection_runs_for_v1_account_without_engine_mode(
        self, mid_v1_account
    ):
        from core.engine.state_machine import STATUS_ACTIVE
        _make_stripe_connection(mid_v1_account)

        sub = Subscriber.objects.create(
            stripe_customer_id="cus_v1_1",
            email="cust@example.com",
            status=STATUS_ACTIVE,
            account=mid_v1_account,
        )

        pi_list = MagicMock()
        pi_list.auto_paging_iter.return_value = []

        sub_list = MagicMock()
        sub_list.auto_paging_iter.return_value = [
            _make_subscription_mock(status="canceled", sub_id="sub_can"),
        ]

        with patch("core.tasks.polling.stripe.PaymentIntent.list", return_value=pi_list), \
             patch("core.tasks.polling.stripe.PaymentIntent.retrieve") as mock_pi_retrieve, \
             patch("core.tasks.polling.stripe.Subscription.list", return_value=sub_list):
            mock_pi_retrieve.side_effect = Exception("not called for non-recovery test")
            poll_account_failures(mid_v1_account.id)

        sub.refresh_from_db()
        assert sub.status == "passive_churn"
        audit = AuditLog.objects.filter(action="subscription_cancellation_detected").first()
        assert audit is not None
        assert audit.metadata["reason"] == "canceled"

    def test_cancel_at_period_end_drives_passive_churn(self, mid_v1_account):
        from core.engine.state_machine import STATUS_ACTIVE
        _make_stripe_connection(mid_v1_account)
        sub = Subscriber.objects.create(
            stripe_customer_id="cus_v1_2",
            email="cust2@example.com",
            status=STATUS_ACTIVE,
            account=mid_v1_account,
        )

        pi_list = MagicMock()
        pi_list.auto_paging_iter.return_value = []
        sub_list = MagicMock()
        sub_list.auto_paging_iter.return_value = [
            _make_subscription_mock(status="active", cancel_at_period_end=True),
        ]

        with patch("core.tasks.polling.stripe.PaymentIntent.list", return_value=pi_list), \
             patch("core.tasks.polling.stripe.Subscription.list", return_value=sub_list):
            poll_account_failures(mid_v1_account.id)

        sub.refresh_from_db()
        assert sub.status == "passive_churn"
        audit = AuditLog.objects.filter(action="subscription_cancellation_detected").first()
        assert audit.metadata["reason"] == "cancel_at_period_end"


class _RecoveryHelperBase(TestCase):
    """TestCase-based so transaction.on_commit callbacks can be exercised
    via captureOnCommitCallbacks.
    """
    pass


@pytest.mark.django_db(transaction=True)
class TestPaymentRecoveryHelper(_RecoveryHelperBase):
    def setUp(self):
        from django.contrib.auth.models import User
        from core.engine.state_machine import STATUS_ACTIVE
        from core.models.account import TIER_MID

        cache.clear()
        self.user = User.objects.create_user(
            username="rec_helper_user",
            email="rec_helper@example.com",
            password="testpass",
        )
        self.account = self.user.account
        self.account.tier = TIER_MID
        self.account.dpa_accepted_at = timezone.now()
        self.account.engine_mode = None
        self.account.save()

        self.subscriber = Subscriber.objects.create(
            account=self.account,
            stripe_customer_id="cus_rec_helper",
            email="rec_helper_sub@example.com",
            status=STATUS_ACTIVE,
        )

    def tearDown(self):
        cache.clear()

    def _make_failure(self, *, pi_id="pi_rec_a", days_ago=1, next_retry_at=None):
        return SubscriberFailure.objects.create(
            account=self.account,
            subscriber=self.subscriber,
            payment_intent_id=pi_id,
            decline_code="insufficient_funds",
            amount_cents=2500,
            classified_action="retry_notify",
            failure_created_at=timezone.now() - timedelta(days=days_ago),
            next_retry_at=next_retry_at,
        )

    @staticmethod
    def _pi(status="succeeded"):
        pi = MagicMock()
        pi.status = status
        return pi

    def test_recovery_detection_active_to_recovered(self):
        failure = self._make_failure()

        with patch("core.tasks.polling.stripe.PaymentIntent.retrieve",
                   return_value=self._pi("succeeded")), \
             patch("core.tasks.notifications.send_recovery_confirmation.delay") as mock_delay, \
             self.captureOnCommitCallbacks(execute=True):
            _check_payment_recoveries(self.account, "sk_test")

        self.subscriber.refresh_from_db()
        self.assertEqual(self.subscriber.status, "recovered")
        audit = AuditLog.objects.filter(action="payment_success_detected").first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.metadata["payment_intent_id"], failure.payment_intent_id)
        self.assertEqual(audit.metadata["failure_id"], str(failure.id))
        mock_delay.assert_called_once_with(failure.id, bypass_engine_active=True)

    def test_recovery_skips_when_pi_still_failing(self):
        self._make_failure()

        with patch("core.tasks.polling.stripe.PaymentIntent.retrieve",
                   return_value=self._pi("requires_payment_method")), \
             patch("core.tasks.notifications.send_recovery_confirmation.delay") as mock_delay, \
             self.captureOnCommitCallbacks(execute=True):
            _check_payment_recoveries(self.account, "sk_test")

        self.subscriber.refresh_from_db()
        self.assertEqual(self.subscriber.status, "active")
        self.assertFalse(AuditLog.objects.filter(action="payment_success_detected").exists())
        mock_delay.assert_not_called()

    def test_recovery_skips_when_subscriber_already_recovered(self):
        self.subscriber.recover()
        self.subscriber.save(update_fields=["status"])
        self._make_failure()

        with patch("core.tasks.polling.stripe.PaymentIntent.retrieve",
                   return_value=self._pi("succeeded")) as mock_retrieve, \
             patch("core.tasks.notifications.send_recovery_confirmation.delay") as mock_delay, \
             self.captureOnCommitCallbacks(execute=True):
            _check_payment_recoveries(self.account, "sk_test")

        # Helper restricts to STATUS_ACTIVE — this subscriber should not be queried.
        mock_retrieve.assert_not_called()
        self.assertFalse(AuditLog.objects.filter(action="payment_success_detected").exists())
        mock_delay.assert_not_called()

    def test_recovery_breaks_after_first_succeeded_pi(self):
        f1 = self._make_failure(pi_id="pi_rec_old", days_ago=10)
        self._make_failure(pi_id="pi_rec_new", days_ago=1)

        with patch("core.tasks.polling.stripe.PaymentIntent.retrieve",
                   return_value=self._pi("succeeded")), \
             patch("core.tasks.notifications.send_recovery_confirmation.delay") as mock_delay, \
             self.captureOnCommitCallbacks(execute=True):
            _check_payment_recoveries(self.account, "sk_test")

        # Exactly one payment_success_detected audit, oldest PI.
        audits = AuditLog.objects.filter(action="payment_success_detected")
        self.assertEqual(audits.count(), 1)
        self.assertEqual(audits.first().metadata["payment_intent_id"], f1.payment_intent_id)
        self.assertEqual(mock_delay.call_count, 1)

    def test_recovery_clears_stale_next_retry_at(self):
        f1 = self._make_failure(
            pi_id="pi_rec_stale",
            next_retry_at=timezone.now() + timedelta(hours=1),
        )

        with patch("core.tasks.polling.stripe.PaymentIntent.retrieve",
                   return_value=self._pi("succeeded")), \
             patch("core.tasks.notifications.send_recovery_confirmation.delay"), \
             self.captureOnCommitCallbacks(execute=True):
            _check_payment_recoveries(self.account, "sk_test")

        f1.refresh_from_db()
        self.assertIsNone(f1.next_retry_at)

    def test_recovery_skips_email_for_free_tier(self):
        from core.models.account import TIER_FREE
        self.account.tier = TIER_FREE
        self.account.save(update_fields=["tier"])
        self._make_failure()

        with patch("core.tasks.polling.stripe.PaymentIntent.retrieve",
                   return_value=self._pi("succeeded")), \
             patch("core.tasks.notifications.send_recovery_confirmation.delay") as mock_delay, \
             self.captureOnCommitCallbacks(execute=True):
            _check_payment_recoveries(self.account, "sk_test")

        self.subscriber.refresh_from_db()
        self.assertEqual(self.subscriber.status, "recovered")
        # FSM transition + payment_success_detected audit happen.
        self.assertTrue(AuditLog.objects.filter(action="payment_success_detected").exists())
        # But the recovery email is NOT dispatched for Free-tier.
        mock_delay.assert_not_called()

    def test_recovery_skips_email_when_no_dpa(self):
        self.account.dpa_accepted_at = None
        self.account.save(update_fields=["dpa_accepted_at"])
        self._make_failure()

        with patch("core.tasks.polling.stripe.PaymentIntent.retrieve",
                   return_value=self._pi("succeeded")), \
             patch("core.tasks.notifications.send_recovery_confirmation.delay") as mock_delay, \
             self.captureOnCommitCallbacks(execute=True):
            _check_payment_recoveries(self.account, "sk_test")

        self.subscriber.refresh_from_db()
        self.assertEqual(self.subscriber.status, "recovered")
        mock_delay.assert_not_called()

    def test_recovery_lookback_window_bounds_pi_calls(self):
        # Failure outside 90-day lookback should not be queried.
        self._make_failure(pi_id="pi_rec_old", days_ago=100)

        with patch("core.tasks.polling.stripe.PaymentIntent.retrieve",
                   return_value=self._pi("succeeded")) as mock_retrieve, \
             patch("core.tasks.notifications.send_recovery_confirmation.delay"), \
             self.captureOnCommitCallbacks(execute=True):
            _check_payment_recoveries(self.account, "sk_test")

        mock_retrieve.assert_not_called()
        self.subscriber.refresh_from_db()
        self.assertEqual(self.subscriber.status, "active")

    def test_stripe_error_during_recovery_check_logs_and_continues(self):
        import stripe
        self._make_failure()

        with patch("core.tasks.polling.stripe.PaymentIntent.retrieve",
                   side_effect=stripe.APIError("boom")), \
             patch("core.tasks.notifications.send_recovery_confirmation.delay") as mock_delay:
            _check_payment_recoveries(self.account, "sk_test")

        self.subscriber.refresh_from_db()
        self.assertEqual(self.subscriber.status, "active")
        self.assertFalse(AuditLog.objects.filter(action="payment_success_detected").exists())
        mock_delay.assert_not_called()


@pytest.mark.django_db
class TestCardUpdateQuarantineGuard:
    """Story 3.4 v1 Task 6.1 — card-update detection stays gated; cancellation +
    recovery helpers are ungated for v1.
    """

    def test_card_update_detection_remains_gated_in_v1(self, mid_v1_account):
        _make_stripe_connection(mid_v1_account)

        pi_list = MagicMock()
        pi_list.auto_paging_iter.return_value = []

        with patch("core.tasks.polling.stripe.PaymentIntent.list", return_value=pi_list), \
             patch("core.tasks.polling._detect_card_updates") as mock_card, \
             patch("core.tasks.polling._check_subscription_cancellations") as mock_cancel, \
             patch("core.tasks.polling._check_payment_recoveries") as mock_recover:
            poll_account_failures(mid_v1_account.id)

        # is_engine_active is False for v1 (engine_mode=None) — card update gated.
        mock_card.assert_not_called()
        # Cancellation + recovery helpers ungated → both called.
        mock_cancel.assert_called_once()
        mock_recover.assert_called_once()
