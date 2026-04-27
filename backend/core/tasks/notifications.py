"""
Celery tasks for sending end-customer notification emails via Resend.

Three discrete email types share the same gate sequence and retry/DLL
machinery: failure_notice, final_notice, recovery_confirmation. The shared
_log_suppression / _record_failure helpers take an explicit email_type so
each task writes a row that is queryable by type.
"""
import logging

from django.db import IntegrityError

from safenet_backend.celery import app
from core.engine.state_machine import STATUS_ACTIVE
from core.models.dead_letter import DeadLetterLog
from core.models.notification import NotificationLog, NotificationOptOut
from core.models.subscriber import Subscriber, SubscriberFailure
from core.services.audit import write_audit_event
from core.services.email import (
    EmailConfigurationError,
    SkipNotification,
    send_final_notice_email,
    send_notification_email,
    send_recovery_confirmation_email,
)
from core.services.tier import is_engine_active

logger = logging.getLogger(__name__)


def _passes_gates(subscriber, failure, account, *, email_type: str, log_label: str) -> bool:
    """Run the shared 5-gate check sequence; return True iff the send may proceed.

    Side-effects: writes NotificationLog + audit rows for each gate that
    rejects, exactly mirroring the existing failure_notice path. Mutating
    helpers are kept inline so each gate's "why we skipped" log line stays
    readable.
    """
    # Gate 1: Engine must be active (Mid/Pro + DPA + engine mode)
    if not is_engine_active(account):
        _log_suppression(subscriber, failure, account, reason="engine_not_active", email_type=email_type)
        return False

    # Gate 2: Subscriber must have a non-blank email
    if not (subscriber.email and subscriber.email.strip()):
        _log_suppression(subscriber, failure, account, reason="no_email", email_type=email_type)
        write_audit_event(
            subscriber=str(subscriber.id),
            actor="engine",
            action="notification_skipped",
            outcome="skipped",
            metadata={"reason": "no_email", "failure_id": str(failure.id), "email_type": email_type},
            account=account,
        )
        logger.info("[%s] SKIPPED no_email failure_id=%s", log_label, failure.id)
        return False

    # Gate 3: Subscriber not excluded from automation
    if subscriber.excluded_from_automation:
        _log_suppression(subscriber, failure, account, reason="excluded_from_automation", email_type=email_type)
        return False

    # Gate 4: Opt-out check (stub for Story 4.4)
    if NotificationOptOut.objects.filter(
        subscriber_email__iexact=subscriber.email.strip(),
        account=account,
    ).exists():
        _log_suppression(subscriber, failure, account, reason="opt_out", email_type=email_type)
        return False

    # Gate 5: Duplicate check — fast-path; the partial unique constraint on
    # (failure, email_type) WHERE status='sent' is the source of truth.
    if NotificationLog.objects.filter(
        failure=failure,
        email_type=email_type,
        status="sent",
        account=account,
    ).exists():
        _log_suppression(subscriber, failure, account, reason="duplicate", email_type=email_type)
        return False

    # Gate 6 (final_notice only): subscriber must still be ACTIVE at task time.
    # AC 3 enforces this at schedule time; re-check here in case the FSM drifted
    # between dispatch and pickup (parallel task moved subscriber to passive_churn
    # or recovered).
    if email_type == "final_notice" and subscriber.status != STATUS_ACTIVE:
        _log_suppression(
            subscriber, failure, account,
            reason="subscriber_not_active", email_type=email_type,
            extra_metadata={"subscriber_status": subscriber.status},
        )
        return False

    return True


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
    email_type = "failure_notice"

    if not _passes_gates(
        subscriber, failure, account,
        email_type=email_type, log_label="send_failure_notification",
    ):
        return

    # All gates passed — send the email
    try:
        msg_id = send_notification_email(subscriber, failure, account)

        try:
            NotificationLog.objects.create(
                account=account,
                subscriber=subscriber,
                failure=failure,
                email_type=email_type,
                resend_message_id=msg_id,
                status="sent",
            )
        except IntegrityError:
            # Partial unique constraint on (failure, email_type) WHERE status='sent'
            # — a parallel task already wrote the success row. Treat as duplicate.
            # Capture msg_id so the duplicate send remains auditable.
            logger.info(
                "[send_failure_notification] DUPLICATE_RACE failure_id=%s msg_id=%s",
                failure_id, msg_id,
            )
            _log_suppression(
                subscriber, failure, account,
                reason="duplicate_race", email_type=email_type,
                extra_metadata={"resend_message_id": msg_id},
            )
            return

        write_audit_event(
            subscriber=str(subscriber.id),
            actor="engine",
            action="notification_sent",
            outcome="success",
            metadata={
                "email_type": email_type,
                "decline_code": failure.decline_code,
                "resend_message_id": msg_id,
            },
            account=account,
        )

        logger.info("[send_failure_notification] COMPLETE failure_id=%s msg_id=%s", failure_id, msg_id)

    except SkipNotification as exc:
        logger.info(
            "[send_failure_notification] SKIPPED failure_id=%s reason=%s",
            failure_id, exc,
        )
        _log_suppression(subscriber, failure, account, reason="skip_permanent", email_type=email_type)
        return

    except EmailConfigurationError as exc:
        logger.error(
            "[send_failure_notification] CONFIG ERROR failure_id=%s error=%s",
            failure_id, exc,
        )
        _record_failure(subscriber, failure, account, exc, email_type=email_type, task_name="send_failure_notification")
        return

    except Exception as exc:
        logger.error("[send_failure_notification] FAILED failure_id=%s error=%s", failure_id, exc)

        if self.request.retries >= self.max_retries:
            _record_failure(subscriber, failure, account, exc, email_type=email_type, task_name="send_failure_notification")
            return

        raise self.retry(exc=exc)


@app.task(bind=True, max_retries=3, default_retry_delay=60)
def send_final_notice(self, failure_id: int):
    """Send a final notice email — the "last attempt" warning before passive churn (FR24)."""
    logger.info("[send_final_notice] START failure_id=%s", failure_id)

    try:
        failure = (
            SubscriberFailure.objects
            .select_related("subscriber", "account", "account__stripe_connection")
            .get(id=failure_id)
        )
    except SubscriberFailure.DoesNotExist:
        logger.error("[send_final_notice] Failure %s not found", failure_id)
        return

    subscriber = failure.subscriber
    account = failure.account
    email_type = "final_notice"

    if not _passes_gates(
        subscriber, failure, account,
        email_type=email_type, log_label="send_final_notice",
    ):
        return

    try:
        msg_id = send_final_notice_email(subscriber, failure, account)

        try:
            NotificationLog.objects.create(
                account=account,
                subscriber=subscriber,
                failure=failure,
                email_type=email_type,
                resend_message_id=msg_id,
                status="sent",
            )
        except IntegrityError:
            logger.info(
                "[send_final_notice] DUPLICATE_RACE failure_id=%s msg_id=%s",
                failure_id, msg_id,
            )
            _log_suppression(
                subscriber, failure, account,
                reason="duplicate_race", email_type=email_type,
                extra_metadata={"resend_message_id": msg_id},
            )
            return

        write_audit_event(
            subscriber=str(subscriber.id),
            actor="engine",
            action="notification_sent",
            outcome="success",
            metadata={
                "email_type": email_type,
                "decline_code": failure.decline_code,
                "resend_message_id": msg_id,
            },
            account=account,
        )

        logger.info("[send_final_notice] COMPLETE failure_id=%s msg_id=%s", failure_id, msg_id)

    except SkipNotification as exc:
        logger.info(
            "[send_final_notice] SKIPPED failure_id=%s reason=%s",
            failure_id, exc,
        )
        _log_suppression(subscriber, failure, account, reason="skip_permanent", email_type=email_type)
        return

    except EmailConfigurationError as exc:
        logger.error(
            "[send_final_notice] CONFIG ERROR failure_id=%s error=%s",
            failure_id, exc,
        )
        _record_failure(subscriber, failure, account, exc, email_type=email_type, task_name="send_final_notice")
        return

    except Exception as exc:
        logger.error("[send_final_notice] FAILED failure_id=%s error=%s", failure_id, exc)

        if self.request.retries >= self.max_retries:
            _record_failure(subscriber, failure, account, exc, email_type=email_type, task_name="send_final_notice")
            return

        raise self.retry(exc=exc)


@app.task(bind=True, max_retries=3, default_retry_delay=60)
def send_recovery_confirmation(self, failure_id: int):
    """Send a recovery confirmation email — short acknowledgement after a successful retry (FR25).

    No CTA, no customer_update_url requirement; the recovery has already happened.
    """
    logger.info("[send_recovery_confirmation] START failure_id=%s", failure_id)

    try:
        failure = (
            SubscriberFailure.objects
            .select_related("subscriber", "account", "account__stripe_connection")
            .get(id=failure_id)
        )
    except SubscriberFailure.DoesNotExist:
        logger.error("[send_recovery_confirmation] Failure %s not found", failure_id)
        return

    subscriber = failure.subscriber
    account = failure.account
    email_type = "recovery_confirmation"

    if not _passes_gates(
        subscriber, failure, account,
        email_type=email_type, log_label="send_recovery_confirmation",
    ):
        return

    try:
        msg_id = send_recovery_confirmation_email(subscriber, failure, account)

        try:
            NotificationLog.objects.create(
                account=account,
                subscriber=subscriber,
                failure=failure,
                email_type=email_type,
                resend_message_id=msg_id,
                status="sent",
            )
        except IntegrityError:
            logger.info(
                "[send_recovery_confirmation] DUPLICATE_RACE failure_id=%s msg_id=%s",
                failure_id, msg_id,
            )
            _log_suppression(
                subscriber, failure, account,
                reason="duplicate_race", email_type=email_type,
                extra_metadata={"resend_message_id": msg_id},
            )
            return

        write_audit_event(
            subscriber=str(subscriber.id),
            actor="engine",
            action="notification_sent",
            outcome="success",
            metadata={
                "email_type": email_type,
                "decline_code": failure.decline_code,
                "resend_message_id": msg_id,
            },
            account=account,
        )

        logger.info("[send_recovery_confirmation] COMPLETE failure_id=%s msg_id=%s", failure_id, msg_id)

    except SkipNotification as exc:
        # Should never fire in practice for recovery_confirmation (no
        # customer_update_url guard), but defensive parity with the other tasks.
        logger.info(
            "[send_recovery_confirmation] SKIPPED failure_id=%s reason=%s",
            failure_id, exc,
        )
        _log_suppression(subscriber, failure, account, reason="skip_permanent", email_type=email_type)
        return

    except EmailConfigurationError as exc:
        logger.error(
            "[send_recovery_confirmation] CONFIG ERROR failure_id=%s error=%s",
            failure_id, exc,
        )
        _record_failure(subscriber, failure, account, exc, email_type=email_type, task_name="send_recovery_confirmation")
        return

    except Exception as exc:
        logger.error("[send_recovery_confirmation] FAILED failure_id=%s error=%s", failure_id, exc)

        if self.request.retries >= self.max_retries:
            _record_failure(subscriber, failure, account, exc, email_type=email_type, task_name="send_recovery_confirmation")
            return

        raise self.retry(exc=exc)


def _log_suppression(
    subscriber, failure, account,
    *,
    reason: str,
    email_type: str = "failure_notice",
    extra_metadata: dict | None = None,
):
    """Log a suppressed notification to NotificationLog and audit trail."""
    metadata = {"reason": reason}
    if extra_metadata:
        metadata.update(extra_metadata)

    NotificationLog.objects.create(
        account=account,
        subscriber=subscriber,
        failure=failure,
        email_type=email_type,
        status="suppressed",
        metadata=metadata,
    )

    write_audit_event(
        subscriber=str(subscriber.id),
        actor="engine",
        action="notification_suppressed",
        outcome="skipped",
        metadata={
            "reason": reason,
            "failure_id": str(failure.id),
            "email_type": email_type,
            **(extra_metadata or {}),
        },
        account=account,
    )

    logger.info(
        "[notifications] SUPPRESSED reason=%s failure_id=%s email_type=%s",
        reason,
        failure.id,
        email_type,
    )


def _record_failure(
    subscriber, failure, account, exc,
    *,
    email_type: str = "failure_notice",
    task_name: str = "send_failure_notification",
):
    """Record a permanent failure to DLL, NotificationLog and audit trail."""
    try:
        DeadLetterLog.objects.create(
            task_name=task_name,
            account=account,
            error=str(exc),
        )
    except Exception:
        logger.exception("[%s] DLL write failed", task_name)

    try:
        NotificationLog.objects.create(
            account=account,
            subscriber=subscriber,
            failure=failure,
            email_type=email_type,
            status="failed",
            metadata={"error": str(exc)},
        )
    except Exception:
        logger.exception("[%s] NotificationLog write failed", task_name)

    try:
        write_audit_event(
            subscriber=str(subscriber.id),
            actor="engine",
            action="notification_failed",
            outcome="failed",
            metadata={
                "email_type": email_type,
                "decline_code": failure.decline_code,
                "error": str(exc),
            },
            account=account,
        )
    except Exception:
        logger.exception("[%s] audit write failed", task_name)
