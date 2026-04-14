"""Tests for retry execution and dispatcher tasks."""
import pytest
from datetime import datetime, timedelta, timezone as dt_tz
from unittest.mock import patch, MagicMock

from core.engine.state_machine import STATUS_ACTIVE, STATUS_RECOVERED, STATUS_PASSIVE_CHURN
from core.models.account import StripeConnection
from core.models.dead_letter import DeadLetterLog
from core.models.subscriber import Subscriber, SubscriberFailure
from core.tasks.retry import execute_retry, execute_pending_retries


@pytest.fixture
def stripe_connection(account):
    return StripeConnection.objects.create(
        account=account,
        stripe_user_id="acct_retry_test",
        _encrypted_access_token="test_token",
    )


@pytest.fixture
def subscriber(account):
    return Subscriber.objects.create(
        stripe_customer_id="cus_retry_task",
        account=account,
    )


@pytest.fixture
def failure(subscriber, account):
    return SubscriberFailure.objects.create(
        subscriber=subscriber,
        account=account,
        payment_intent_id="pi_retry_task",
        decline_code="insufficient_funds",
        amount_cents=5000,
        failure_created_at=datetime(2026, 1, 1, tzinfo=dt_tz.utc),
        classified_action="retry_notify",
    )


@pytest.mark.django_db
class TestExecuteRetry:

    @patch("core.tasks.retry.stripe.PaymentIntent.confirm")
    @patch("core.models.account.StripeConnection.access_token", new_callable=lambda: property(lambda self: "sk_test_mock"))
    def test_successful_retry_recovers_subscriber(self, mock_token, mock_confirm, failure, stripe_connection):
        mock_confirm.return_value = MagicMock(status="succeeded")
        with patch("core.services.recovery.write_audit_event"):
            result = execute_retry(failure.id)
        assert result["success"] is True
        failure.subscriber.refresh_from_db()
        assert failure.subscriber.status == STATUS_RECOVERED

    @patch("core.tasks.retry.stripe.PaymentIntent.confirm")
    @patch("core.models.account.StripeConnection.access_token", new_callable=lambda: property(lambda self: "sk_test_mock"))
    def test_failed_retry_increments_count(self, mock_token, mock_confirm, failure, stripe_connection):
        mock_confirm.return_value = MagicMock(status="requires_payment_method")
        with patch("core.services.recovery.write_audit_event"):
            result = execute_retry(failure.id)
        assert result["success"] is False
        failure.refresh_from_db()
        assert failure.retry_count == 1

    def test_missing_failure_skips(self):
        result = execute_retry(99999)
        assert result["skipped"] is True
        assert result["reason"] == "not_found"

    def test_non_active_subscriber_skips(self, failure, stripe_connection):
        failure.subscriber.status = "recovered"
        Subscriber.objects.filter(pk=failure.subscriber.pk).update(status="recovered")
        result = execute_retry(failure.id)
        assert result["skipped"] is True
        assert result["reason"] == "not_active"

    @patch("core.tasks.retry.stripe.PaymentIntent.confirm")
    @patch("core.models.account.StripeConnection.access_token", new_callable=lambda: property(lambda self: "sk_test_mock"))
    def test_unhandled_exception_writes_dead_letter(self, mock_token, mock_confirm, failure, stripe_connection):
        mock_confirm.side_effect = RuntimeError("unexpected")
        with pytest.raises(RuntimeError):
            execute_retry(failure.id)
        dead = DeadLetterLog.objects.filter(task_name="execute_retry").first()
        assert dead is not None
        assert "unexpected" in dead.error

    @patch("core.tasks.retry.stripe.PaymentIntent.confirm")
    @patch("core.models.account.StripeConnection.access_token", new_callable=lambda: property(lambda self: "sk_test_mock"))
    def test_stripe_error_treated_as_failed_retry(self, mock_token, mock_confirm, failure, stripe_connection):
        import stripe as stripe_mod
        mock_confirm.side_effect = stripe_mod.StripeError("rate limited")
        with patch("core.services.recovery.write_audit_event"):
            result = execute_retry(failure.id)
        assert result["success"] is False


@pytest.mark.django_db
class TestExecutePendingRetries:

    def test_dispatches_due_retries(self, failure, account):
        failure.next_retry_at = datetime(2020, 1, 1, tzinfo=dt_tz.utc)
        failure.save()

        with patch("core.tasks.retry.execute_retry") as mock_task:
            mock_task.delay = MagicMock()
            result = execute_pending_retries()
        assert result["dispatched"] == 1
        mock_task.delay.assert_called_once_with(failure.id)

    def test_skips_non_active_subscribers(self, failure, account):
        failure.next_retry_at = datetime(2020, 1, 1, tzinfo=dt_tz.utc)
        failure.save()
        Subscriber.objects.filter(pk=failure.subscriber.pk).update(status="recovered")

        with patch("core.tasks.retry.execute_retry") as mock_task:
            mock_task.delay = MagicMock()
            result = execute_pending_retries()
        assert result["dispatched"] == 0

    def test_skips_future_retries(self, failure, account):
        failure.next_retry_at = datetime(2099, 1, 1, tzinfo=dt_tz.utc)
        failure.save()

        with patch("core.tasks.retry.execute_retry") as mock_task:
            mock_task.delay = MagicMock()
            result = execute_pending_retries()
        assert result["dispatched"] == 0
