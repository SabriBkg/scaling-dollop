"""Tests for polling task recovery integration (Tasks 7, 8, 9)."""
import pytest
from datetime import datetime, timezone as dt_tz
from unittest.mock import patch, MagicMock, PropertyMock

from core.engine.state_machine import STATUS_ACTIVE, STATUS_PASSIVE_CHURN, STATUS_FRAUD_FLAGGED
from core.models.account import Account, StripeConnection, TIER_MID
from core.models.subscriber import Subscriber, SubscriberFailure
from core.tasks.polling import _process_autopilot_recovery, _check_subscription_cancellations


@pytest.fixture
def account_autopilot(account):
    account.tier = TIER_MID
    account.dpa_accepted_at = datetime(2026, 1, 1, tzinfo=dt_tz.utc)
    account.engine_mode = "autopilot"
    account.save()
    return account


@pytest.fixture
def subscriber(account_autopilot):
    return Subscriber.objects.create(
        stripe_customer_id="cus_poll_test",
        account=account_autopilot,
    )


@pytest.fixture
def failure_retry(subscriber, account_autopilot):
    return SubscriberFailure.objects.create(
        subscriber=subscriber,
        account=account_autopilot,
        payment_intent_id="pi_poll_retry",
        decline_code="insufficient_funds",
        amount_cents=5000,
        failure_created_at=datetime(2026, 1, 1, tzinfo=dt_tz.utc),
        classified_action="retry_notify",
        payment_method_country="US",
    )


@pytest.fixture
def failure_fraud(subscriber, account_autopilot):
    return SubscriberFailure.objects.create(
        subscriber=subscriber,
        account=account_autopilot,
        payment_intent_id="pi_poll_fraud",
        decline_code="fraudulent",
        amount_cents=5000,
        failure_created_at=datetime(2026, 1, 1, tzinfo=dt_tz.utc),
        classified_action="fraud_flag",
    )


@pytest.fixture
def failure_eu(account_autopilot):
    sub = Subscriber.objects.create(
        stripe_customer_id="cus_poll_eu",
        account=account_autopilot,
    )
    return SubscriberFailure.objects.create(
        subscriber=sub,
        account=account_autopilot,
        payment_intent_id="pi_poll_eu",
        decline_code="insufficient_funds",
        amount_cents=5000,
        failure_created_at=datetime(2026, 1, 1, tzinfo=dt_tz.utc),
        classified_action="retry_notify",
        payment_method_country="DE",
    )


@pytest.mark.django_db
class TestAutopilotRecoveryProcessing:

    def test_retry_notify_schedules_retry(self, failure_retry, account_autopilot):
        with patch("core.services.recovery.write_audit_event"):
            _process_autopilot_recovery(failure_retry, account_autopilot)
        failure_retry.refresh_from_db()
        assert failure_retry.next_retry_at is not None

    def test_fraud_flag_transitions_subscriber(self, failure_fraud, account_autopilot):
        _process_autopilot_recovery(failure_fraud, account_autopilot)
        failure_fraud.subscriber.refresh_from_db()
        assert failure_fraud.subscriber.status == STATUS_FRAUD_FLAGGED

    def test_geo_compliance_override_eu_payment(self, failure_eu, account_autopilot):
        """EU payment → notify_only override, geo_compliance_override audit logged."""
        with patch("core.tasks.polling.write_audit_event") as mock_audit:
            with patch("core.services.recovery.write_audit_event"):
                _process_autopilot_recovery(failure_eu, account_autopilot)

            geo_calls = [c for c in mock_audit.call_args_list
                         if c.kwargs.get("action") == "geo_compliance_override"]
            assert len(geo_calls) == 1
            assert geo_calls[0].kwargs["metadata"]["payment_method_country"] == "DE"

    def test_fraud_flag_stops_all_further_actions(self, failure_fraud, account_autopilot):
        """After fraud flag, subscriber should not be retryable."""
        _process_autopilot_recovery(failure_fraud, account_autopilot)
        failure_fraud.subscriber.refresh_from_db()
        assert failure_fraud.subscriber.status == STATUS_FRAUD_FLAGGED
        # No retry should be scheduled
        failure_fraud.refresh_from_db()
        assert failure_fraud.next_retry_at is None


@pytest.mark.django_db
class TestSubscriptionCancellationDetection:

    @patch("core.tasks.polling.stripe.Subscription.list")
    def test_cancelled_subscription_transitions_to_passive_churn(
        self, mock_sub_list, subscriber, account_autopilot
    ):
        mock_sub = MagicMock()
        mock_sub.status = "canceled"
        mock_sub.id = "sub_cancelled"
        mock_sub.cancel_at_period_end = False
        mock_sub_list.return_value = MagicMock(auto_paging_iter=MagicMock(return_value=[mock_sub]))

        _check_subscription_cancellations(account_autopilot, "sk_test")
        subscriber.refresh_from_db()
        assert subscriber.status == STATUS_PASSIVE_CHURN

    @patch("core.tasks.polling.stripe.Subscription.list")
    def test_cancel_at_period_end_transitions_to_passive_churn(
        self, mock_sub_list, subscriber, account_autopilot
    ):
        mock_sub = MagicMock()
        mock_sub.status = "active"
        mock_sub.id = "sub_cancel_end"
        mock_sub.cancel_at_period_end = True
        mock_sub_list.return_value = MagicMock(auto_paging_iter=MagicMock(return_value=[mock_sub]))

        _check_subscription_cancellations(account_autopilot, "sk_test")
        subscriber.refresh_from_db()
        assert subscriber.status == STATUS_PASSIVE_CHURN

    @patch("core.tasks.polling.stripe.Subscription.list")
    def test_cancellation_clears_pending_retries(
        self, mock_sub_list, subscriber, account_autopilot
    ):
        failure = SubscriberFailure.objects.create(
            subscriber=subscriber,
            account=account_autopilot,
            payment_intent_id="pi_cancel_retry",
            decline_code="insufficient_funds",
            amount_cents=1000,
            failure_created_at=datetime(2026, 1, 1, tzinfo=dt_tz.utc),
            classified_action="retry_notify",
            next_retry_at=datetime(2026, 2, 1, tzinfo=dt_tz.utc),
        )

        mock_sub = MagicMock()
        mock_sub.status = "canceled"
        mock_sub.id = "sub_cancelled"
        mock_sub.cancel_at_period_end = False
        mock_sub_list.return_value = MagicMock(auto_paging_iter=MagicMock(return_value=[mock_sub]))

        _check_subscription_cancellations(account_autopilot, "sk_test")
        failure.refresh_from_db()
        assert failure.next_retry_at is None

    @patch("core.tasks.polling.stripe.Subscription.list")
    def test_unpaid_subscription_transitions(self, mock_sub_list, subscriber, account_autopilot):
        mock_sub = MagicMock()
        mock_sub.status = "unpaid"
        mock_sub.id = "sub_unpaid"
        mock_sub.cancel_at_period_end = False
        mock_sub_list.return_value = MagicMock(auto_paging_iter=MagicMock(return_value=[mock_sub]))

        _check_subscription_cancellations(account_autopilot, "sk_test")
        subscriber.refresh_from_db()
        assert subscriber.status == STATUS_PASSIVE_CHURN

    @patch("core.tasks.polling.stripe.Subscription.list")
    def test_active_subscription_no_transition(self, mock_sub_list, subscriber, account_autopilot):
        mock_sub = MagicMock()
        mock_sub.status = "active"
        mock_sub.id = "sub_active"
        mock_sub.cancel_at_period_end = False
        mock_sub_list.return_value = MagicMock(auto_paging_iter=MagicMock(return_value=[mock_sub]))

        _check_subscription_cancellations(account_autopilot, "sk_test")
        subscriber.refresh_from_db()
        assert subscriber.status == STATUS_ACTIVE
