"""
Recovery execution orchestrator.

Takes a SubscriberFailure + RecoveryDecision and executes the correct action.
This is the Django-side bridge between the pure-Python engine and ORM models.

RULE: Engine isolation — core/engine/ has ZERO Django imports.
All ORM work happens here in core/services/.
"""
import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from django_fsm import TransitionNotAllowed

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


def _safe_transition(subscriber, transition_name, account):
    """
    Attempt an FSM transition, catching TransitionNotAllowed if the subscriber
    was concurrently transitioned by another task. Logs an audit event on conflict.

    Returns True if the transition succeeded, False if it was blocked.
    """
    method = getattr(subscriber, transition_name)
    try:
        method()
        subscriber.save()
        return True
    except TransitionNotAllowed:
        logger.warning(
            "FSM transition %s blocked for subscriber %s (current status: %s)",
            transition_name, subscriber.id, subscriber.status,
        )
        write_audit_event(
            subscriber=str(subscriber.id),
            actor="engine",
            action=f"transition_blocked_{transition_name}",
            outcome="skipped",
            metadata={
                "current_status": subscriber.status,
                "attempted_transition": transition_name,
            },
            account=account,
        )
        return False


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
        transitioned = _safe_transition(subscriber, "mark_fraud_flagged", account)
        write_audit_event(
            subscriber=str(subscriber.id),
            actor="engine",
            action="recovery_fraud_flagged",
            outcome="success" if transitioned else "skipped",
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
        # Clear stale next_retry_at so this failure doesn't appear in pending queries
        failure.next_retry_at = None
        failure.save(update_fields=["next_retry_at"])

        if subscriber.status == STATUS_ACTIVE:
            _safe_transition(subscriber, "mark_passive_churn", account)
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

    # Final notice (FR24): the dispatch fires when the retry being scheduled is
    # the LAST one permitted by the rule. retry_count is the count BEFORE this
    # retry executes; the upcoming retry is retry_count + 1.
    is_last_retry = (failure.retry_count + 1) == decision.retry_cap
    if is_last_retry and decision.retry_cap > 0:
        # Status guard: if the subscriber has drifted out of ACTIVE between the
        # cap-exhaustion branch above and here, suppress the final notice — the
        # FSM has already moved past active and the email would mislead.
        if subscriber.status != STATUS_ACTIVE:
            logger.info(
                "[schedule_retry] Skipping final notice — subscriber %s is %s",
                subscriber.id, subscriber.status,
            )
            return

        # Idempotency guard: if a final_notice has already been logged for this
        # failure (sent or suppressed_duplicate), do not re-dispatch. Concurrent
        # operators / replay / parallel polling can otherwise register two
        # on_commit lambdas → two Resend.send calls before the unique
        # constraint fires.
        from core.models.notification import NotificationLog
        if NotificationLog.objects.filter(
            failure=failure,
            email_type="final_notice",
            status__in=["sent", "suppressed"],
        ).exists():
            logger.info(
                "[schedule_retry] Skipping final notice — already dispatched for failure %s",
                failure.id,
            )
            return

        from core.tasks.notifications import send_final_notice
        failure_id = failure.id
        transaction.on_commit(
            lambda fid=failure_id: send_final_notice.delay(fid)
        )

        write_audit_event(
            subscriber=str(subscriber.id),
            actor="engine",
            action="final_notice_dispatched",
            outcome="success",
            metadata={
                "decline_code": decision.decline_code,
                "retry_number": failure.retry_count + 1,
                "retry_cap": decision.retry_cap,
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

        transitioned = False
        if subscriber.status == STATUS_ACTIVE:
            transitioned = _safe_transition(subscriber, "recover", account)

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

        # Recovery confirmation (FR25): dispatch only if the FSM transition
        # actually occurred. If the subscriber was already non-ACTIVE (status
        # drift, parallel task, manual operator action), the transition
        # returns False and we do not send a confirmation.
        # 5-minute SLA per FR25; no countdown= needed — Celery worker picks
        # up immediately and the Resend send completes well under 5 min.
        if transitioned:
            from core.tasks.notifications import send_recovery_confirmation
            failure_id = failure.id
            transaction.on_commit(
                lambda fid=failure_id: send_recovery_confirmation.delay(fid)
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
