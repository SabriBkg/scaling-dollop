"""
Celery task for sending failure notification emails via Resend.

Triggered by the polling pipeline when classified_action includes notification.
Handles gate checks, retry logic, dead-lettering, and audit trail.
"""
import logging

from safenet_backend.celery import app
from core.models.dead_letter import DeadLetterLog
from core.models.notification import NotificationLog, NotificationOptOut
from core.models.subscriber import Subscriber, SubscriberFailure
from core.services.audit import write_audit_event
from core.services.email import send_notification_email
from core.services.tier import is_engine_active

logger = logging.getLogger(__name__)


@app.task(bind=True, max_retries=3, default_retry_delay=60)
def send_failure_notification(self, failure_id: int):
    """Send a branded payment failure notification email for a given failure."""
    logger.info("[send_failure_notification] START failure_id=%s", failure_id)

    try:
        failure = (
            SubscriberFailure.objects
            .select_related("subscriber", "account", "account__stripe_connection")
            .get(id=failure_id)
        )
    except SubscriberFailure.DoesNotExist:
        logger.error("[send_failure_notification] Failure %s not found", failure_id)
        return

    subscriber = failure.subscriber
    account = failure.account

    # Gate 1: Engine must be active (Mid/Pro + DPA + engine mode)
    if not is_engine_active(account):
        _log_suppression(subscriber, failure, account, reason="engine_not_active")
        return

    # Gate 2: Subscriber must have an email
    if not subscriber.email:
        write_audit_event(
            subscriber=str(subscriber.id),
            actor="engine",
            action="notification_skipped",
            outcome="skipped",
            metadata={"reason": "no_email", "failure_id": str(failure.id)},
            account=account,
        )
        logger.info("[send_failure_notification] SKIPPED no_email failure_id=%s", failure_id)
        return

    # Gate 3: Subscriber not excluded from automation
    if subscriber.excluded_from_automation:
        _log_suppression(subscriber, failure, account, reason="excluded_from_automation")
        return

    # Gate 4: Opt-out check (stub for Story 4.4)
    if NotificationOptOut.objects.filter(
        subscriber_email=subscriber.email,
        account=account,
    ).exists():
        _log_suppression(subscriber, failure, account, reason="opt_out")
        return

    # Gate 5: Duplicate check — don't re-send for same failure + email_type
    if NotificationLog.objects.filter(
        failure=failure,
        email_type="failure_notice",
        status="sent",
        account=account,
    ).exists():
        _log_suppression(subscriber, failure, account, reason="duplicate")
        return

    # All gates passed — send the email
    try:
        msg_id = send_notification_email(subscriber, failure, account)

        NotificationLog.objects.create(
            account=account,
            subscriber=subscriber,
            failure=failure,
            email_type="failure_notice",
            resend_message_id=msg_id,
            status="sent",
        )

        write_audit_event(
            subscriber=str(subscriber.id),
            actor="engine",
            action="notification_sent",
            outcome="success",
            metadata={
                "email_type": "failure_notice",
                "decline_code": failure.decline_code,
                "resend_message_id": msg_id,
            },
            account=account,
        )

        logger.info("[send_failure_notification] COMPLETE failure_id=%s msg_id=%s", failure_id, msg_id)

    except Exception as exc:
        logger.error("[send_failure_notification] FAILED failure_id=%s error=%s", failure_id, exc)

        if self.request.retries >= self.max_retries:
            DeadLetterLog.objects.create(
                task_name="send_failure_notification",
                account=account,
                error=str(exc),
            )

            NotificationLog.objects.create(
                account=account,
                subscriber=subscriber,
                failure=failure,
                email_type="failure_notice",
                status="failed",
                metadata={"error": str(exc)},
            )

            write_audit_event(
                subscriber=str(subscriber.id),
                actor="engine",
                action="notification_failed",
                outcome="failed",
                metadata={
                    "email_type": "failure_notice",
                    "decline_code": failure.decline_code,
                    "error": str(exc),
                },
                account=account,
            )
            return

        raise self.retry(exc=exc)


def _log_suppression(subscriber, failure, account, reason: str):
    """Log a suppressed notification to NotificationLog and audit trail."""
    NotificationLog.objects.create(
        account=account,
        subscriber=subscriber,
        failure=failure,
        email_type="failure_notice",
        status="suppressed",
        metadata={"reason": reason},
    )

    write_audit_event(
        subscriber=str(subscriber.id),
        actor="engine",
        action="notification_suppressed",
        outcome="skipped",
        metadata={
            "reason": reason,
            "failure_id": str(failure.id),
            "email_type": "failure_notice",
        },
        account=account,
    )

    logger.info(
        "[send_failure_notification] SUPPRESSED reason=%s failure_id=%s",
        reason,
        failure.id,
    )
