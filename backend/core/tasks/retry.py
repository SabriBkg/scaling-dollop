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


@app.task(bind=True, max_retries=3, default_retry_delay=60)
def execute_retry(self, failure_id):
    """
    Execute a single retry attempt for a failed payment.
    Confirms the PaymentIntent via Stripe API and processes the result.
    """
    logger.info("START execute_retry failure_id=%s", failure_id)

    try:
        failure = (
            SubscriberFailure.objects
            .select_related("subscriber", "account")
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
        process_retry_result(failure, success=success)
        logger.info("COMPLETE execute_retry failure_id=%s success=%s", failure_id, success)
        return {"failure_id": failure_id, "success": success}

    except stripe.StripeError as exc:
        # Stripe API error — treat as failed retry
        logger.warning(
            "Stripe error during retry for failure %s: %s", failure_id, str(exc)
        )
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
        .select_related("subscriber")
        .filter(
            next_retry_at__lte=now,
            subscriber__status=STATUS_ACTIVE,
        )
    )

    dispatched = 0
    for failure in pending:
        execute_retry.delay(failure.id)
        dispatched += 1

    logger.info("COMPLETE execute_pending_retries dispatched=%d", dispatched)
    return {"dispatched": dispatched}
