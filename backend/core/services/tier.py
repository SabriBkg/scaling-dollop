"""
Tier gating service for subscription-level access control.

All tier checks should go through this module — never inline tier comparisons
in views or tasks.
"""
from django.utils import timezone

from core.models.account import TIER_FREE, TIER_MID, TIER_PRO

# Polling intervals in seconds
POLLING_FREQ_HOURLY = 3600  # Mid/Pro
POLLING_FREQ_TWICE_MONTHLY = 1_296_000  # ~15 days, Free tier


def get_polling_frequency(account) -> int:
    """Returns seconds between polls based on account tier."""
    if account.tier == TIER_FREE:
        return POLLING_FREQ_TWICE_MONTHLY
    return POLLING_FREQ_HOURLY


def is_engine_active(account) -> bool:
    """True only when Mid/Pro tier, DPA accepted, and engine mode selected."""
    return (
        account.tier in (TIER_MID, TIER_PRO)
        and account.dpa_accepted
        and account.engine_mode is not None
    )


def check_and_degrade_trial(account) -> bool:
    """
    If account is on an expired Mid trial, downgrade to Free.
    Returns True if degradation occurred.
    """
    if account.tier != TIER_MID:
        return False
    if account.trial_ends_at is None:
        return False
    if account.is_on_trial:
        return False
    # Trial expired: trial_ends_at is in the past
    account.tier = TIER_FREE
    account.save(update_fields=["tier"])
    return True


def upgrade_to_mid(account) -> None:
    """Upgrade account to Mid tier, clearing any trial period."""
    account.tier = TIER_MID
    account.trial_ends_at = None
    account.save(update_fields=["tier", "trial_ends_at"])
