"""
Retroactive 90-day failure scan task.
Queued immediately after a new Stripe Connect OAuth authorization.
"""
import logging
from datetime import timedelta

import stripe
from django.utils import timezone

from safenet_backend.celery import app
from core.models.account import Account, StripeConnection
from core.services.audit import write_audit_event
from core.services.failure_ingestion import ingest_failed_payment

logger = logging.getLogger(__name__)


@app.task(bind=True, max_retries=5, default_retry_delay=60)
def scan_retroactive_failures(self, account_id):
    """
    Scan the last 90 days of failed payment intents for a newly connected account.
    Idempotent — safe to re-run without duplicating records.
    """
    account = Account.objects.get(id=account_id)
    connection = StripeConnection.objects.get(account=account)
    access_token = connection.access_token

    ninety_days_ago = timezone.now() - timedelta(days=90)
    created_gte = int(ninety_days_ago.timestamp())

    total_processed = 0
    total_created = 0
    total_errors = 0

    try:
        payment_intents = stripe.PaymentIntent.list(
            api_key=access_token,
            created={"gte": created_gte},
            limit=100,
        )

        for pi in payment_intents.auto_paging_iter():
            # Only process declined payments (requires_payment_method = declined)
            if pi.status != "requires_payment_method":
                continue

            try:
                _, _, created = ingest_failed_payment(account, pi)
                total_processed += 1
                if created:
                    total_created += 1
            except Exception:
                pi_id = getattr(pi, "id", "unknown")
                logger.exception("Failed to ingest payment intent %s for account %s", pi_id, account_id)
                total_errors += 1

    except stripe.error.RateLimitError as exc:
        logger.warning("Rate limited during retroactive scan for account %s, retrying", account_id)
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 30)
    except Exception as exc:
        write_audit_event(
            subscriber=None,
            actor="engine",
            action="retroactive_scan_failed",
            outcome="failed",
            account=account,
            metadata={"error": str(exc), "account_id": account_id},
        )
        raise

    write_audit_event(
        subscriber=None,
        actor="engine",
        action="retroactive_scan_completed",
        outcome="success",
        account=account,
        metadata={
            "total_processed": total_processed,
            "total_created": total_created,
            "total_errors": total_errors,
            "account_id": account_id,
        },
    )

    return {"processed": total_processed, "created": total_created}
