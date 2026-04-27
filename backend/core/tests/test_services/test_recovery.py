"""Tests for recovery execution service."""
import pytest
from datetime import datetime, timezone as dt_tz
from unittest.mock import patch, MagicMock

from core.engine.processor import RecoveryDecision
from core.engine.state_machine import (
    STATUS_ACTIVE,
    STATUS_RECOVERED,
    STATUS_PASSIVE_CHURN,
    STATUS_FRAUD_FLAGGED,
)
from core.models.subscriber import Subscriber, SubscriberFailure
from core.services.recovery import (
    execute_recovery_action,
    schedule_retry,
    process_retry_result,
)


def _make_decision(action="retry_notify", decline_code="insufficient_funds",
                   retry_cap=3, payday_aware=False, geo_blocked=False):
    return RecoveryDecision(
        decline_code=decline_code,
        action=action,
        retry_cap=retry_cap,
        payday_aware=payday_aware,
        geo_blocked=geo_blocked,
        rule={"action": action, "retry_cap": retry_cap, "payday_aware": payday_aware, "geo_block": False},
    )


@pytest.fixture
def subscriber(account):
    return Subscriber.objects.create(
        stripe_customer_id="cus_recovery_test",
        account=account,
    )


@pytest.fixture
def failure(subscriber, account):
    return SubscriberFailure.objects.create(
        subscriber=subscriber,
        account=account,
        payment_intent_id="pi_recovery_test",
        decline_code="insufficient_funds",
        amount_cents=5000,
        failure_created_at=datetime(2026, 1, 1, tzinfo=dt_tz.utc),
        classified_action="retry_notify",
    )


@pytest.mark.django_db
class TestExecuteRecoveryAction:

    def test_fraud_flag_transitions_subscriber(self, failure, account):
        decision = _make_decision(action="fraud_flag", decline_code="fraudulent", retry_cap=0)
        execute_recovery_action(failure, decision, account)
        failure.subscriber.refresh_from_db()
        assert failure.subscriber.status == STATUS_FRAUD_FLAGGED

    def test_no_action_writes_audit_only(self, failure, account):
        decision = _make_decision(action="no_action", decline_code="some_code", retry_cap=0)
        with patch("core.services.recovery.write_audit_event") as mock_audit:
            execute_recovery_action(failure, decision, account)
            mock_audit.assert_called_once()
            assert mock_audit.call_args.kwargs["action"] == "recovery_no_action"

    def test_notify_only_writes_audit(self, failure, account):
        decision = _make_decision(action="notify_only", decline_code="expired_card",
                                  retry_cap=0, geo_blocked=True)
        with patch("core.services.recovery.write_audit_event") as mock_audit:
            execute_recovery_action(failure, decision, account)
            mock_audit.assert_called_once()
            assert mock_audit.call_args.kwargs["action"] == "recovery_notify_only"
            assert mock_audit.call_args.kwargs["metadata"]["geo_blocked"] is True

    def test_retry_notify_schedules_retry(self, failure, account):
        decision = _make_decision(action="retry_notify", retry_cap=3, payday_aware=False)
        with patch("core.services.recovery.write_audit_event"):
            execute_recovery_action(failure, decision, account)
        failure.refresh_from_db()
        assert failure.next_retry_at is not None


@pytest.mark.django_db
class TestScheduleRetry:

    def test_retry_cap_exhausted_transitions_to_passive_churn(self, failure, account):
        failure.retry_count = 3
        failure.save()
        decision = _make_decision(retry_cap=3)
        with patch("core.services.recovery.write_audit_event"):
            schedule_retry(failure, decision)
        failure.subscriber.refresh_from_db()
        assert failure.subscriber.status == STATUS_PASSIVE_CHURN

    def test_payday_aware_schedules_at_payday_window(self, failure, account):
        decision = _make_decision(payday_aware=True, retry_cap=3)
        with patch("core.services.recovery.write_audit_event"):
            schedule_retry(failure, decision)
        failure.refresh_from_db()
        assert failure.next_retry_at is not None
        assert failure.next_retry_at.day in (1, 15)

    def test_non_payday_schedules_with_delay(self, failure, account):
        decision = _make_decision(payday_aware=False, retry_cap=3)
        with patch("core.services.recovery.write_audit_event"):
            schedule_retry(failure, decision)
        failure.refresh_from_db()
        assert failure.next_retry_at is not None

    def test_audit_event_on_schedule(self, failure, account):
        decision = _make_decision(retry_cap=3)
        with patch("core.services.recovery.write_audit_event") as mock_audit:
            schedule_retry(failure, decision)
            calls = [c for c in mock_audit.call_args_list
                     if c.kwargs.get("action") == "retry_scheduled"]
            assert len(calls) == 1


@pytest.mark.django_db
class TestProcessRetryResult:

    def test_success_recovers_subscriber(self, failure, account):
        with patch("core.services.recovery.write_audit_event"):
            process_retry_result(failure, success=True)
        failure.subscriber.refresh_from_db()
        assert failure.subscriber.status == STATUS_RECOVERED
        failure.refresh_from_db()
        assert failure.retry_count == 1
        assert failure.next_retry_at is None
        assert failure.last_retry_at is not None

    def test_failure_increments_retry_count(self, failure, account):
        with patch("core.services.recovery.write_audit_event"):
            process_retry_result(failure, success=False)
        failure.refresh_from_db()
        assert failure.retry_count == 1
        assert failure.last_retry_at is not None

    def test_failure_schedules_next_retry(self, failure, account):
        with patch("core.services.recovery.write_audit_event"):
            process_retry_result(failure, success=False)
        failure.refresh_from_db()
        assert failure.next_retry_at is not None

    def test_failure_at_cap_transitions_to_passive_churn(self, failure, account):
        # insufficient_funds has retry_cap=3, set to 2 so after increment it hits 3
        failure.retry_count = 2
        failure.save()
        with patch("core.services.recovery.write_audit_event"):
            process_retry_result(failure, success=False)
        failure.refresh_from_db()
        assert failure.retry_count == 3
        failure.subscriber.refresh_from_db()
        assert failure.subscriber.status == STATUS_PASSIVE_CHURN


# ---------------------------------------------------------------------------
# Story 4.3 — final notice & recovery confirmation dispatch
# ---------------------------------------------------------------------------


@pytest.fixture
def mid_active_account(account):
    """Account configured to keep the engine active (Mid + DPA + autopilot)."""
    from django.utils import timezone
    from core.models.account import TIER_MID
    account.tier = TIER_MID
    account.dpa_accepted_at = timezone.now()
    account.engine_mode = "autopilot"
    account.company_name = "TestCo"
    account.save()
    return account


@pytest.mark.django_db(transaction=True)
class TestFinalNoticeDispatch:
    """Final notice dispatches from schedule_retry on the LAST permitted retry."""

    @patch("core.tasks.notifications.send_final_notice.delay")
    def test_dispatched_on_last_retry(self, mock_delay, failure, mid_active_account):
        # retry_cap=3, retry_count=2 → upcoming retry is #3 → IS last
        failure.retry_count = 2
        failure.save()
        decision = _make_decision(retry_cap=3)

        from django.db import transaction as django_transaction
        with django_transaction.atomic():
            schedule_retry(failure, decision)
        mock_delay.assert_called_once_with(failure.id)

    @patch("core.tasks.notifications.send_final_notice.delay")
    def test_not_dispatched_when_not_last_retry(self, mock_delay, failure, mid_active_account):
        failure.retry_count = 0
        failure.save()
        decision = _make_decision(retry_cap=3)

        from django.db import transaction as django_transaction
        with django_transaction.atomic():
            schedule_retry(failure, decision)
        mock_delay.assert_not_called()

    @patch("core.tasks.notifications.send_final_notice.delay")
    def test_not_dispatched_when_retry_cap_zero(self, mock_delay, failure, mid_active_account):
        """retry_cap=0 means cap-exhausted branch fires; no final notice."""
        failure.retry_count = 0
        failure.save()
        decision = _make_decision(retry_cap=0)

        from django.db import transaction as django_transaction
        with django_transaction.atomic():
            schedule_retry(failure, decision)
        mock_delay.assert_not_called()
        # Subscriber should be transitioned to passive_churn (cap-exhausted path)
        failure.subscriber.refresh_from_db()
        assert failure.subscriber.status == STATUS_PASSIVE_CHURN

    @patch("core.tasks.notifications.send_final_notice.delay")
    def test_not_dispatched_when_subscriber_inactive(self, mock_delay, failure, mid_active_account):
        # Force subscriber out of ACTIVE without going through FSM, then refresh
        # so the schedule_retry path sees the drift in `subscriber.status`.
        Subscriber.objects.filter(id=failure.subscriber_id).update(status=STATUS_RECOVERED)
        failure.subscriber.refresh_from_db()
        failure.retry_count = 2
        failure.save()
        decision = _make_decision(retry_cap=3)

        from django.db import transaction as django_transaction
        with django_transaction.atomic():
            schedule_retry(failure, decision)
        mock_delay.assert_not_called()

    @patch("core.tasks.notifications.send_final_notice.delay")
    def test_dispatched_after_commit(self, mock_delay, failure, mid_active_account):
        """on_commit dispatch must NOT fire if surrounding atomic block rolls back."""
        failure.retry_count = 2
        failure.save()
        decision = _make_decision(retry_cap=3)

        from django.db import transaction as django_transaction
        try:
            with django_transaction.atomic():
                schedule_retry(failure, decision)
                raise RuntimeError("force rollback")
        except RuntimeError:
            pass
        mock_delay.assert_not_called()

    @patch("core.tasks.notifications.send_final_notice.delay")
    def test_dispatched_when_retry_cap_one(self, mock_delay, failure, mid_active_account):
        """retry_cap=1: the FIRST retry IS the last retry."""
        failure.retry_count = 0
        failure.save()
        decision = _make_decision(retry_cap=1)

        from django.db import transaction as django_transaction
        with django_transaction.atomic():
            schedule_retry(failure, decision)
        mock_delay.assert_called_once_with(failure.id)

    def test_writes_final_notice_dispatched_audit(self, failure, mid_active_account):
        from core.models.audit import AuditLog
        failure.retry_count = 2
        failure.save()
        decision = _make_decision(retry_cap=3, decline_code="insufficient_funds")

        from django.db import transaction as django_transaction
        with patch("core.tasks.notifications.send_final_notice.delay"):
            with django_transaction.atomic():
                schedule_retry(failure, decision)

        audit = AuditLog.objects.filter(action="final_notice_dispatched").first()
        assert audit is not None
        assert audit.outcome == "success"
        assert audit.metadata["retry_cap"] == 3
        assert audit.metadata["retry_number"] == 3
        assert audit.metadata["decline_code"] == "insufficient_funds"
        assert audit.metadata["failure_id"] == str(failure.id)


@pytest.mark.django_db(transaction=True)
class TestRecoveryConfirmationDispatch:
    """Recovery confirmation dispatches from process_retry_result on successful recovery."""

    @patch("core.tasks.notifications.send_recovery_confirmation.delay")
    def test_dispatched_on_successful_recover(self, mock_delay, failure, mid_active_account):
        from django.db import transaction as django_transaction
        with django_transaction.atomic():
            process_retry_result(failure, success=True)

        mock_delay.assert_called_once_with(failure.id)
        failure.subscriber.refresh_from_db()
        assert failure.subscriber.status == STATUS_RECOVERED

    @patch("core.tasks.notifications.send_recovery_confirmation.delay")
    def test_not_dispatched_on_failed_retry(self, mock_delay, failure, mid_active_account):
        from django.db import transaction as django_transaction
        with django_transaction.atomic():
            process_retry_result(failure, success=False)

        mock_delay.assert_not_called()

    @patch("core.tasks.notifications.send_recovery_confirmation.delay")
    def test_not_dispatched_when_already_recovered(self, mock_delay, failure, mid_active_account):
        Subscriber.objects.filter(id=failure.subscriber_id).update(status=STATUS_RECOVERED)
        failure.subscriber.refresh_from_db()

        from django.db import transaction as django_transaction
        with django_transaction.atomic():
            process_retry_result(failure, success=True)

        mock_delay.assert_not_called()

    @patch("core.tasks.notifications.send_recovery_confirmation.delay")
    @patch("core.services.recovery._safe_transition", return_value=False)
    def test_not_dispatched_when_transition_blocked(self, mock_transition, mock_delay,
                                                     failure, mid_active_account):
        from django.db import transaction as django_transaction
        with django_transaction.atomic():
            process_retry_result(failure, success=True)

        mock_delay.assert_not_called()

    @patch("core.tasks.notifications.send_recovery_confirmation.delay")
    def test_idempotent_per_failure(self, mock_delay, failure, mid_active_account):
        """Second process_retry_result call after recovery does not re-dispatch.

        Idempotency mechanism: after the first call the subscriber is in
        STATUS_RECOVERED, so the second call's `_safe_transition(active→recovered)`
        returns False, `transitioned` stays False, and the on_commit hook is
        never registered. This test pins both the dispatch count and the
        underlying FSM precondition.
        """
        from django.db import transaction as django_transaction
        with django_transaction.atomic():
            process_retry_result(failure, success=True)

        failure.subscriber.refresh_from_db()
        assert failure.subscriber.status == STATUS_RECOVERED, (
            "first call must leave subscriber in RECOVERED for the FSM-based "
            "idempotency guard on the second call to engage"
        )

        # Second call: subscriber is already RECOVERED → transition returns False
        with django_transaction.atomic():
            process_retry_result(failure, success=True)

        assert mock_delay.call_count == 1

    @patch("core.tasks.notifications.send_recovery_confirmation.delay")
    def test_dispatched_after_commit(self, mock_delay, failure, mid_active_account):
        """on_commit dispatch must NOT fire if surrounding atomic block rolls back."""
        from django.db import transaction as django_transaction
        try:
            with django_transaction.atomic():
                process_retry_result(failure, success=True)
                raise RuntimeError("force rollback")
        except RuntimeError:
            pass
        mock_delay.assert_not_called()
