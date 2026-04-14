"""
Tests for Supervised mode polling integration.
Verifies PendingAction creation and fraud exception.
"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone as dt_tz

from django.utils import timezone

from core.engine.state_machine import STATUS_ACTIVE, STATUS_FRAUD_FLAGGED
from core.models.account import Account
from core.models.audit import AuditLog
from core.models.pending_action import PendingAction
from core.models.subscriber import Subscriber, SubscriberFailure
from core.tasks.polling import _process_supervised_queue


@pytest.mark.django_db
class TestSupervisedPollingQueue:
    @pytest.fixture
    def supervised_account(self, account):
        account.tier = "mid"
        account.dpa_accepted_at = timezone.now()
        account.engine_mode = "supervised"
        account.save()
        return account

    @pytest.fixture
    def subscriber(self, supervised_account):
        return Subscriber.objects.create(
            account=supervised_account,
            stripe_customer_id="cus_test_123",
            email="sub@example.com",
        )

    @pytest.fixture
    def failure(self, supervised_account, subscriber):
        return SubscriberFailure.objects.create(
            account=supervised_account,
            subscriber=subscriber,
            payment_intent_id="pi_test_001",
            decline_code="insufficient_funds",
            amount_cents=5000,
            failure_created_at=timezone.now(),
            classified_action="retry_notify",
        )

    @pytest.fixture
    def fraud_failure(self, supervised_account, subscriber):
        return SubscriberFailure.objects.create(
            account=supervised_account,
            subscriber=subscriber,
            payment_intent_id="pi_test_fraud",
            decline_code="fraudulent",
            amount_cents=9999,
            failure_created_at=timezone.now(),
            classified_action="fraud_flag",
        )

    def test_supervised_creates_pending_action(self, supervised_account, failure):
        """AC1: New failure in supervised mode creates PendingAction, not immediate execution."""
        _process_supervised_queue(failure, supervised_account)

        pa = PendingAction.objects.for_account(supervised_account.id).first()
        assert pa is not None
        assert pa.subscriber == failure.subscriber
        assert pa.failure == failure
        assert pa.recommended_action == "retry_notify"
        assert pa.status == "pending"

    def test_supervised_does_not_execute_recovery(self, supervised_account, failure):
        """AC1: Supervised mode does NOT call execute_recovery_action."""
        with patch("core.services.recovery.execute_recovery_action") as mock_exec:
            _process_supervised_queue(failure, supervised_account)
            mock_exec.assert_not_called()

    def test_supervised_writes_audit_event(self, supervised_account, failure):
        """Audit trail: action_queued_supervised event created."""
        _process_supervised_queue(failure, supervised_account)

        log = AuditLog.objects.filter(action="action_queued_supervised").first()
        assert log is not None
        assert log.metadata["failure_id"] == str(failure.id)
        assert log.metadata["recommended_action"] == "retry_notify"

    def test_fraud_executes_immediately_in_supervised(self, supervised_account, fraud_failure):
        """Fraud exception: fraud_flag actions execute immediately, never queued."""
        _process_supervised_queue(fraud_failure, supervised_account)

        assert PendingAction.objects.for_account(supervised_account.id).count() == 0
        fraud_failure.subscriber.refresh_from_db()
        assert fraud_failure.subscriber.status == STATUS_FRAUD_FLAGGED

    def test_excluded_subscriber_not_queued(self, supervised_account, subscriber, failure):
        """AC4: Excluded subscribers do not get PendingActions."""
        subscriber.excluded_from_automation = True
        subscriber.save()

        _process_supervised_queue(failure, supervised_account)
        assert PendingAction.objects.for_account(supervised_account.id).count() == 0
