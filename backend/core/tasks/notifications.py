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
from core.services.email import (
    EmailConfigurationError,
    SkipNotification,
    send_notification_email,
)
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

    # Gate 2: Subscriber must have a non-blank email
    if not (subscriber.email and subscriber.email.strip()):
        _log_suppression(subscriber, failure, account, reason="no_email")
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
    # Case-insensitive + whitespace-trimmed lookup so that opt-outs honour
    # the address regardless of how it was originally entered.
    if NotificationOptOut.objects.filter(
        subscriber_email__iexact=subscriber.email.strip(),
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

    except SkipNotification as exc:
        # Permanent skip (e.g. account missing customer-update URL). Don't
        # retry — record as suppressed and move on.
        logger.info(
            "[send_failure_notification] SKIPPED failure_id=%s reason=%s",
            failure_id, exc,
        )
        _log_suppression(subscriber, failure, account, reason="skip_permanent")
        return

    except EmailConfigurationError as exc:
        # Misconfiguration — retries can't help. Dead-letter immediately so
        # operators see the alert without a 3-retry delay.
        logger.error(
            "[send_failure_notification] CONFIG ERROR failure_id=%s error=%s",
            failure_id, exc,
        )
        _record_failure(subscriber, failure, account, exc)
        return

    except Exception as exc:
        # Transient / unknown error — retry up to max_retries, then dead-letter.
        # Programming errors (AttributeError, KeyError, etc.) will land here too,
        # but they will surface clearly in the DLL row after retries exhaust.
        logger.error("[send_failure_notification] FAILED failure_id=%s error=%s", failure_id, exc)

        if self.request.retries >= self.max_retries:
            _record_failure(subscriber, failure, account, exc)
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


def _record_failure(subscriber, failure, account, exc):
    """Record a permanent failure to DLL, NotificationLog and audit trail."""
    try:
        DeadLetterLog.objects.create(
            task_name="send_failure_notification",
            account=account,
            error=str(exc),
        )
    except Exception:
        logger.exception("[send_failure_notification] DLL write failed")

    try:
        NotificationLog.objects.create(
            account=account,
            subscriber=subscriber,
            failure=failure,
            email_type="failure_notice",
            status="failed",
            metadata={"error": str(exc)},
        )
    except Exception:
        logger.exception("[send_failure_notification] NotificationLog write failed")

    try:
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
    except Exception:
        logger.exception("[send_failure_notification] audit write failed")
