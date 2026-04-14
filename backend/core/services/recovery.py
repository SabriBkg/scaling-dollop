"""
Recovery execution orchestrator.

Takes a SubscriberFailure + RecoveryDecision and executes the correct action.
This is the Django-side bridge between the pure-Python engine and ORM models.

RULE: Engine isolation — core/engine/ has ZERO Django imports.
All ORM work happens here in core/services/.
"""
import logging
from datetime import timedelta

from django.utils import timezone

from core.engine.payday import next_payday_retry_window
from core.engine.processor import RecoveryDecision
from core.engine.state_machine import (
    ACTION_FRAUD_FLAG,
    ACTION_NO_ACTION,
    ACTION_NOTIFY_ONLY,
    ACTION_RETRY_NOTIFY,
    STATUS_ACTIVE,
)
from core.services.audit import write_audit_event

logger = logging.getLogger(__name__)

# Default delay for non-payday-aware retries
DEFAULT_RETRY_DELAY_SECONDS = 3600  # 1 hour


def execute_recovery_action(failure, decision: RecoveryDecision, account):
    """
    Execute the recovery action determined by the rule engine.

    Args:
        failure: SubscriberFailure instance
        decision: RecoveryDecision from get_recovery_action()
        account: Account instance (for audit trail)
    """
    subscriber = failure.subscriber
    action = decision.action

    if action == ACTION_FRAUD_FLAG:
        subscriber.mark_fraud_flagged()
        subscriber.save()
        write_audit_event(
            subscriber=str(subscriber.id),
            actor="engine",
            action="recovery_fraud_flagged",
            outcome="success",
            metadata={
                "decline_code": decision.decline_code,
                "failure_id": str(failure.id),
            },
            account=account,
        )
        return

    if action == ACTION_NO_ACTION:
        write_audit_event(
            subscriber=str(subscriber.id),
            actor="engine",
            action="recovery_no_action",
            outcome="success",
            metadata={
                "decline_code": decision.decline_code,
                "failure_id": str(failure.id),
            },
            account=account,
        )
        return

    if action == ACTION_NOTIFY_ONLY:
        # Notification stub for Epic 4 — log audit event now
        write_audit_event(
            subscriber=str(subscriber.id),
            actor="engine",
            action="recovery_notify_only",
            outcome="success",
            metadata={
                "decline_code": decision.decline_code,
                "failure_id": str(failure.id),
                "geo_blocked": decision.geo_blocked,
            },
            account=account,
        )
        return

    if action == ACTION_RETRY_NOTIFY:
        schedule_retry(failure, decision)
        # Notification stub for Epic 4
        write_audit_event(
            subscriber=str(subscriber.id),
            actor="engine",
            action="recovery_retry_notify",
            outcome="success",
            metadata={
                "decline_code": decision.decline_code,
                "failure_id": str(failure.id),
                "retry_count": failure.retry_count,
                "next_retry_at": failure.next_retry_at.isoformat() if failure.next_retry_at else None,
            },
            account=account,
        )
        return


def schedule_retry(failure, decision: RecoveryDecision):
    """
    Schedule the next retry for a failure, or transition to passive_churn if cap exhausted.

    Args:
        failure: SubscriberFailure instance
        decision: RecoveryDecision with retry_cap and payday_aware info
    """
    subscriber = failure.subscriber
    account = failure.account

    # Check retry cap
    if failure.retry_count >= decision.retry_cap:
        if subscriber.status == STATUS_ACTIVE:
            subscriber.mark_passive_churn()
            subscriber.save()
        write_audit_event(
            subscriber=str(subscriber.id),
            actor="engine",
            action="retry_cap_exhausted",
            outcome="success",
            metadata={
                "decline_code": decision.decline_code,
                "retry_count": failure.retry_count,
                "retry_cap": decision.retry_cap,
                "failure_id": str(failure.id),
            },
            account=account,
        )
        return

    # Calculate next_retry_at
    now = timezone.now()
    if decision.payday_aware:
        window_start, _ = next_payday_retry_window(now.date())
        next_retry_at = window_start
    else:
        next_retry_at = now + timedelta(seconds=DEFAULT_RETRY_DELAY_SECONDS)

    failure.next_retry_at = next_retry_at
    failure.save(update_fields=["next_retry_at"])

    write_audit_event(
        subscriber=str(subscriber.id),
        actor="engine",
        action="retry_scheduled",
        outcome="success",
        metadata={
            "decline_code": decision.decline_code,
            "retry_number": failure.retry_count + 1,
            "next_retry_at": next_retry_at.isoformat(),
            "payday_aware": decision.payday_aware,
            "failure_id": str(failure.id),
        },
        account=account,
    )


def process_retry_result(failure, success: bool):
    """
    Process the result of a retry attempt.

    Args:
        failure: SubscriberFailure instance
        success: True if Stripe confirms payment succeeded
    """
    subscriber = failure.subscriber
    account = failure.account
    now = timezone.now()

    failure.retry_count += 1
    failure.last_retry_at = now

    if success:
        failure.next_retry_at = None
        failure.save(update_fields=["retry_count", "last_retry_at", "next_retry_at"])

        if subscriber.status == STATUS_ACTIVE:
            subscriber.recover()
            subscriber.save()

        write_audit_event(
            subscriber=str(subscriber.id),
            actor="engine",
            action="retry_succeeded",
            outcome="success",
            metadata={
                "decline_code": failure.decline_code,
                "retry_count": failure.retry_count,
                "failure_id": str(failure.id),
                "payment_intent_id": failure.payment_intent_id,
            },
            account=account,
        )
    else:
        failure.save(update_fields=["retry_count", "last_retry_at"])

        write_audit_event(
            subscriber=str(subscriber.id),
            actor="engine",
            action="retry_failed",
            outcome="failed",
            metadata={
                "decline_code": failure.decline_code,
                "retry_count": failure.retry_count,
                "failure_id": str(failure.id),
                "payment_intent_id": failure.payment_intent_id,
            },
            account=account,
        )

        # Re-derive decision to check cap and schedule next retry
        from core.engine.processor import get_recovery_action

        decision = get_recovery_action(
            failure.decline_code,
            payment_method_country=failure.payment_method_country,
        )
        schedule_retry(failure, decision)
