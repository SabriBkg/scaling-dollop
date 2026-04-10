"""
Hourly polling task for new payment failures across all accounts.
Registered with Celery beat at 3600-second intervals.
"""
import logging
from datetime import timedelta

import stripe
from django.core.cache import cache
from django.utils import timezone

from safenet_backend.celery import app
from core.models.account import Account, StripeConnection
from core.services.audit import write_audit_event
from core.services.failure_ingestion import ingest_failed_payment

logger = logging.getLogger(__name__)

POLL_LAST_RUN_KEY = "poll:last_run:{account_id}"
MISSED_CYCLE_THRESHOLD_MINUTES = 90
# 48-hour TTL so cache survives extended outages without suppressing missed-cycle alerts
POLL_CACHE_TTL = 48 * 3600


@app.task(bind=True)
def poll_new_failures(self):
    """
    Dispatch per-account polling subtasks for all active accounts.
    Each account is polled in isolation so one failure cannot block others.
    """
    connections = StripeConnection.objects.select_related("account").all()
    account_ids = [conn.account_id for conn in connections]

    for account_id in account_ids:
        poll_account_failures.delay(account_id)

    logger.info("Dispatched polling subtasks for %d accounts", len(account_ids))
    return {"accounts_dispatched": len(account_ids)}


@app.task(bind=True, max_retries=5, default_retry_delay=60)
def poll_account_failures(self, account_id):
    """
    Poll a single account for new failed payment intents since last poll.
    Isolated per-account — rate limits and errors do not affect other accounts.
    """
    try:
        connection = StripeConnection.objects.select_related("account").get(account_id=account_id)
    except StripeConnection.DoesNotExist:
        logger.warning("StripeConnection not found for account %s, skipping poll", account_id)
        return {"account_id": account_id, "skipped": True}

    account = connection.account
    cache_key = POLL_LAST_RUN_KEY.format(account_id=account_id)

    # Check for missed cycle (AC5: alert within 90 minutes)
    last_run_ts = cache.get(cache_key)
    if last_run_ts:
        elapsed_minutes = (timezone.now() - last_run_ts).total_seconds() / 60
        if elapsed_minutes > MISSED_CYCLE_THRESHOLD_MINUTES:
            write_audit_event(
                subscriber=None,
                actor="engine",
                action="polling_cycle_missed",
                outcome="alert",
                account=account,
                metadata={"gap_minutes": round(elapsed_minutes, 1), "account_id": account_id},
            )
            logger.warning(
                "Polling cycle missed for account %s — gap of %.1f minutes",
                account_id,
                elapsed_minutes,
            )

    # Determine time window
    if last_run_ts:
        created_gte = int(last_run_ts.timestamp())
    else:
        # First poll — look back 90 minutes to catch any gap
        fallback = timezone.now() - timedelta(minutes=90)
        created_gte = int(fallback.timestamp())

    access_token = connection.access_token
    total_created = 0

    try:
        payment_intents = stripe.PaymentIntent.list(
            api_key=access_token,
            created={"gte": created_gte},
            limit=100,
        )

        for pi in payment_intents.auto_paging_iter():
            if pi.status != "requires_payment_method":
                continue

            _, _, created = ingest_failed_payment(account, pi)
            if created:
                total_created += 1

    except stripe.error.RateLimitError as exc:
        logger.warning("Rate limited during polling for account %s, retrying", account_id)
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 30)

    # Mark successful poll time
    cache.set(cache_key, timezone.now(), timeout=POLL_CACHE_TTL)

    write_audit_event(
        subscriber=None,
        actor="engine",
        action="polling_cycle_completed",
        outcome="success",
        account=account,
        metadata={
            "account_id": account_id,
            "new_failures_created": total_created,
        },
    )

    return {"account_id": account_id, "new_failures": total_created}
