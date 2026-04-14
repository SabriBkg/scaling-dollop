"""
Daily task to expire trial accounts that have passed their trial_ends_at date.
"""
import logging

from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from safenet_backend.celery import app
from core.models.account import Account, TIER_MID
from core.services.audit import write_audit_event
from core.services.tier import check_and_degrade_trial

logger = logging.getLogger(__name__)


@app.task(bind=True)
def expire_trials(self):
    """
    Find all Mid-tier accounts whose trial has expired and downgrade to Free.
    Runs daily via Celery beat.
    """
    expired_account_ids = list(
        Account.objects.filter(
            tier=TIER_MID,
            trial_ends_at__lte=timezone.now(),
        ).exclude(trial_ends_at__isnull=True).values_list("id", flat=True)
    )

    expired_count = 0
    for account_id in expired_account_ids:
        try:
            with transaction.atomic():
                account = Account.objects.select_for_update().get(id=account_id)
                if check_and_degrade_trial(account):
                    cache.delete(f"dashboard_summary_{account.id}")
                    write_audit_event(
                        subscriber=None,
                        actor="engine",
                        action="trial_expired",
                        outcome="success",
                        account=account,
                    )
                    expired_count += 1
                    logger.info("Trial expired for account %s, downgraded to Free", account.id)
        except Account.DoesNotExist:
            logger.warning("Account %s disappeared during trial expiration", account_id)

    logger.info("Trial expiration job complete: %d accounts expired", expired_count)
    return {"expired_count": expired_count}
