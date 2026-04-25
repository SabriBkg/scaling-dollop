"""
Retry execution and dispatch tasks for the recovery engine.
Registered with Celery beat for periodic retry processing.
"""
import logging

import stripe
from django.db import transaction
from django.utils import timezone

from safenet_backend.celery import app
from core.engine.state_machine import STATUS_ACTIVE
from core.models.account import StripeConnection
from core.models.dead_letter import DeadLetterLog
from core.models.subscriber import SubscriberFailure
from core.services.recovery import process_retry_result

logger = logging.getLogger(__name__)

# Stripe error types that are transient and should use Celery retry
# rather than burning a business retry count
TRANSIENT_STRIPE_ERRORS = (
    stripe.RateLimitError,
    stripe.APIConnectionError,
)


@app.task(bind=True, max_retries=3, default_retry_delay=60)
def execute_retry(self, failure_id):
    """
    Execute a single retry attempt for a failed payment.
    Confirms the PaymentIntent via Stripe API and processes the result.
    """
    logger.info("START execute_retry failure_id=%s", failure_id)

    # Look up the failure inside an atomic block so select_for_update() is
    # legal. The lock is released as soon as the block exits — we only need
    # it to prevent two concurrent workers from picking the same row.
    try:
        with transaction.atomic():
            failure = (
                SubscriberFailure.objects
                .select_related("subscriber", "account")
                .select_for_update()
                .get(id=failure_id)
            )
    except SubscriberFailure.DoesNotExist:
        logger.warning("SubscriberFailure %s not found, skipping retry", failure_id)
        return {"failure_id": failure_id, "skipped": True, "reason": "not_found"}

    # Guard: only retry active subscribers
    if failure.subscriber.status != STATUS_ACTIVE:
        logger.info(
            "Subscriber %s status is %s, skipping retry for failure %s",
            failure.subscriber.id, failure.subscriber.status, failure_id,
        )
        return {"failure_id": failure_id, "skipped": True, "reason": "not_active"}

    try:
        connection = StripeConnection.objects.get(account=failure.account)
    except StripeConnection.DoesNotExist:
        logger.warning("StripeConnection not found for account %s", failure.account_id)
        return {"failure_id": failure_id, "skipped": True, "reason": "no_connection"}

    try:
        result = stripe.PaymentIntent.confirm(
            failure.payment_intent_id,
            api_key=connection.access_token,
        )
        success = result.status == "succeeded"
        with transaction.atomic():
            process_retry_result(failure, success=success)
        logger.info("COMPLETE execute_retry failure_id=%s success=%s", failure_id, success)
        return {"failure_id": failure_id, "success": success}

    except TRANSIENT_STRIPE_ERRORS as exc:
        # Transient Stripe errors — use Celery retry, don't burn business retry count
        logger.warning(
            "Transient Stripe error during retry for failure %s: %s, Celery retry %d/%d",
            failure_id, str(exc), self.request.retries, self.max_retries,
        )
        raise self.retry(exc=exc)

    except stripe.StripeError as exc:
        # Permanent Stripe error — treat as failed retry
        logger.warning(
            "Stripe error during retry for failure %s: %s", failure_id, str(exc)
        )
        with transaction.atomic():
            process_retry_result(failure, success=False)
        return {"failure_id": failure_id, "success": False, "error": str(exc)}

    except Exception as exc:
        # Dead letter on unhandled exception
        logger.error("FAILED execute_retry failure_id=%s error=%s", failure_id, str(exc))
        DeadLetterLog.objects.create(
            account=failure.account,
            task_name="execute_retry",
            error=f"failure_id={failure_id} error={exc!r}",
        )
        raise


@app.task(bind=True)
def execute_pending_retries(self):
    """
    Periodic task: find all failures due for retry and dispatch individual retry tasks.
    Runs every 15 minutes via Celery beat.
    """
    logger.info("START execute_pending_retries")

    now = timezone.now()
    pending = (
        SubscriberFailure.objects
        .select_related("subscriber", "account")
        .filter(
            next_retry_at__lte=now,
            subscriber__status=STATUS_ACTIVE,
        )
    )

    dispatched = 0
    for failure in pending:
        # Per-failure dispatch errors are attributable to a specific account,
        # so write a DeadLetterLog with proper tenant scoping (NFR-R5).
        try:
            execute_retry.delay(failure.id)
            dispatched += 1
        except Exception as exc:
            logger.error(
                "FAILED to dispatch retry for failure_id=%s account=%s error=%s",
                failure.id, failure.account_id, exc,
            )
            try:
                DeadLetterLog.objects.create(
                    account=failure.account,
                    task_name="execute_pending_retries",
                    error=f"dispatch_failed failure_id={failure.id} error={exc!r}",
                )
            except Exception:
                logger.exception(
                    "DeadLetterLog write failed for failure_id=%s", failure.id,
                )
            continue

    logger.info("COMPLETE execute_pending_retries dispatched=%d", dispatched)
    return {"dispatched": dispatched}
