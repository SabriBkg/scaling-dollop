"""
Decline-code rule engine configuration.

Maps every known Stripe decline code to a recovery rule.
This is the single source of truth for all SafeNet recovery behaviour.

Rule schema:
    action:       "retry_notify" | "notify_only" | "fraud_flag" | "no_action"
    retry_cap:    int — maximum retry attempts (0 = no retries)
    payday_aware: bool — if True, schedule retry in payday window (1st/15th +24h)
    geo_block:    bool — if True, EU/UK contexts must override action to "notify_only"

Adding a new code: add one entry here. Zero business logic changes required.
Unknown codes fall through to "_default" — never fraud-flags, always conservative.

Source: Stripe decline code documentation + FR10, FR11, FR12, FR13.
"""

from typing import TypedDict


class DeclineRule(TypedDict):
    action: str        # "retry_notify" | "notify_only" | "fraud_flag" | "no_action"
    retry_cap: int     # 0 = no retries
    payday_aware: bool # schedule within payday window if True
    geo_block: bool    # True = EU/UK must override to notify_only


# ---------------------------------------------------------------------------
# Master configuration — 30+ Stripe decline codes
# ---------------------------------------------------------------------------
DECLINE_RULES: dict[str, DeclineRule] = {

    # --- Insufficient funds (FR11: payday-aware scheduling, FR12: 3 retries) ---
    "insufficient_funds": {
        "action": "retry_notify",
        "retry_cap": 3,
        "payday_aware": True,
        "geo_block": True,
    },

    # --- Card expired — no retry possible, notify only (FR12: 0 retries) ---
    "expired_card": {
        "action": "notify_only",
        "retry_cap": 0,
        "payday_aware": False,
        "geo_block": False,
    },
    "card_expired": {  # alternate code used by some issuers
        "action": "notify_only",
        "retry_cap": 0,
        "payday_aware": False,
        "geo_block": False,
    },

    # --- Fraud-flagged codes (FR19: stop all actions immediately) ---
    "fraudulent": {
        "action": "fraud_flag",
        "retry_cap": 0,
        "payday_aware": False,
        "geo_block": False,
    },
    "lost_card": {
        "action": "fraud_flag",
        "retry_cap": 0,
        "payday_aware": False,
        "geo_block": False,
    },
    "stolen_card": {
        "action": "fraud_flag",
        "retry_cap": 0,
        "payday_aware": False,
        "geo_block": False,
    },
    "pickup_card": {
        "action": "fraud_flag",
        "retry_cap": 0,
        "payday_aware": False,
        "geo_block": False,
    },

    # --- 2-retry category (FR12: do_not_honor / generic_decline = 2 retries) ---
    "do_not_honor": {
        "action": "retry_notify",
        "retry_cap": 2,
        "payday_aware": False,
        "geo_block": True,
    },
    "generic_decline": {
        "action": "retry_notify",
        "retry_cap": 2,
        "payday_aware": False,
        "geo_block": True,
    },

    # --- 1-retry category (FR12: card_velocity_exceeded = 1 retry) ---
    "card_velocity_exceeded": {
        "action": "retry_notify",
        "retry_cap": 1,
        "payday_aware": False,
        "geo_block": False,
    },

    # --- Notify-only codes: card update required ---
    "new_account_information_available": {
        "action": "notify_only",
        "retry_cap": 0,
        "payday_aware": False,
        "geo_block": False,
    },
    "card_not_supported": {
        "action": "notify_only",
        "retry_cap": 0,
        "payday_aware": False,
        "geo_block": False,
    },
    "currency_not_supported": {
        "action": "notify_only",
        "retry_cap": 0,
        "payday_aware": False,
        "geo_block": False,
    },
    "service_not_allowed": {
        "action": "notify_only",
        "retry_cap": 0,
        "payday_aware": False,
        "geo_block": False,
    },
    "transaction_not_allowed": {
        "action": "notify_only",
        "retry_cap": 0,
        "payday_aware": False,
        "geo_block": False,
    },
    "not_permitted": {
        "action": "notify_only",
        "retry_cap": 0,
        "payday_aware": False,
        "geo_block": False,
    },
    "restricted_card": {
        "action": "notify_only",
        "retry_cap": 0,
        "payday_aware": False,
        "geo_block": False,
    },
    "security_violation": {
        "action": "notify_only",
        "retry_cap": 0,
        "payday_aware": False,
        "geo_block": False,
    },
    "stop_payment_order": {
        "action": "notify_only",
        "retry_cap": 0,
        "payday_aware": False,
        "geo_block": False,
    },
    "revocation_of_authorization": {
        "action": "notify_only",
        "retry_cap": 0,
        "payday_aware": False,
        "geo_block": False,
    },
    "revocation_of_all_authorizations": {
        "action": "notify_only",
        "retry_cap": 0,
        "payday_aware": False,
        "geo_block": False,
    },
    "invalid_account": {
        "action": "notify_only",
        "retry_cap": 0,
        "payday_aware": False,
        "geo_block": False,
    },

    # --- Retry codes: transient / recoverable ---
    "processing_error": {
        "action": "retry_notify",
        "retry_cap": 1,
        "payday_aware": False,
        "geo_block": False,
    },
    "try_again_later": {
        "action": "retry_notify",
        "retry_cap": 1,
        "payday_aware": False,
        "geo_block": False,
    },
    "reenter_transaction": {
        "action": "retry_notify",
        "retry_cap": 1,
        "payday_aware": False,
        "geo_block": False,
    },
    "no_action_taken": {
        "action": "retry_notify",
        "retry_cap": 1,
        "payday_aware": False,
        "geo_block": False,
    },
    "duplicate_transaction": {
        "action": "retry_notify",
        "retry_cap": 1,
        "payday_aware": False,
        "geo_block": False,
    },
    "invalid_amount": {
        "action": "retry_notify",
        "retry_cap": 1,
        "payday_aware": False,
        "geo_block": False,
    },

    # --- PIN-related: notify only (requires physical interaction) ---
    "incorrect_pin": {
        "action": "notify_only",
        "retry_cap": 0,
        "payday_aware": False,
        "geo_block": False,
    },
    "incorrect_cvc": {
        "action": "notify_only",
        "retry_cap": 0,
        "payday_aware": False,
        "geo_block": False,
    },
    "pin_try_exceeded": {
        "action": "notify_only",
        "retry_cap": 0,
        "payday_aware": False,
        "geo_block": False,
    },
    "offline_pin_required": {
        "action": "notify_only",
        "retry_cap": 0,
        "payday_aware": False,
        "geo_block": False,
    },
    "online_or_offline_pin_required": {
        "action": "notify_only",
        "retry_cap": 0,
        "payday_aware": False,
        "geo_block": False,
    },

    # --- Catch-all default (FR12: all other codes = 1 retry) ---
    # CRITICAL: Never set action="fraud_flag" here — unknown codes must not auto-flag fraud.
    "_default": {
        "action": "retry_notify",
        "retry_cap": 1,
        "payday_aware": False,
        "geo_block": False,
    },
}


def get_rule(decline_code: str | None) -> DeclineRule:
    """
    Look up the rule for a decline code.
    Falls through to _default for any unknown code or None.
    Never raises KeyError.
    """
    if not decline_code:
        return dict(DECLINE_RULES["_default"])
    return dict(DECLINE_RULES.get(decline_code.lower().strip(), DECLINE_RULES["_default"]))
