"""
Decline-code rule engine configuration.

Maps every known Stripe decline code to a recovery rule.
This is the single source of truth for all SafeNet recovery behaviour.

Rule schema (v0 fields — preserved unchanged for v2 retry-engine reactivation):
    action:       "retry_notify" | "notify_only" | "fraud_flag" | "no_action"
    retry_cap:    int — maximum retry attempts (0 = no retries)
    payday_aware: bool — if True, schedule retry in payday window (1st/15th +24h)
    geo_block:    bool — if True, EU/UK contexts must override action to "notify_only"

Rule schema (v1 fields — Story 3.5 v1 recommended-email mapping, FR10):
    recommended_email: "update_payment" | "retry_reminder" | "final_notice" | None
                       — the kind of recommendation this code supports.
                       None means the rule produces "no_recommendation" (fraud or
                       inherently un-actionable). Non-None means the actual
                       recommendation is computed at serialization time from
                       days-since-failure (see ``get_recommended_email``).
                       Architecture line 253: escalation is applied at serialization
                       time, not baked into DECLINE_RULES.
    fraud_flag:        bool — if True, get_recommended_email returns "fraud_flag"
                       regardless of days-since-failure. The dashboard wire-form
                       maps this to null / "—".
    geo_warning:       bool — informational EU/UK context flag. v1: surfaced as
                       a sidecar chip on the dashboard. Does NOT change the
                       recommendation, sort, or action availability.

v0 / v1 separation contract: Story 3.5 v1 ADDS the v1 keys; it does NOT delete,
rename, or change the value of any v0 key. The v2 quarantine branch
(archive/v0-recovery-engine) reactivates the v0 keys — any drift here forces a
re-derivation there.

Adding a new code: add one entry here with all seven keys. Zero business logic
changes required. Unknown codes fall through to "_default" — never fraud-flags,
always conservative.

Source: Stripe decline code documentation + FR10, FR11, FR12, FR13.
"""

from typing import TypedDict


class DeclineRule(TypedDict):
    # --- v0 fields (preserved unchanged for v2 retry-engine reactivation) ---
    action: str        # "retry_notify" | "notify_only" | "fraud_flag" | "no_action"
    retry_cap: int     # 0 = no retries
    payday_aware: bool # schedule within payday window if True
    geo_block: bool    # True = EU/UK must override to notify_only
    # --- v1 fields (Story 3.5 v1 — recommended-email mapping, FR10) ---
    recommended_email: str | None  # "update_payment" | "retry_reminder" | "final_notice" | None
    fraud_flag: bool               # True = get_recommended_email returns "fraud_flag"
    geo_warning: bool              # informational EU/UK context flag


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
        "recommended_email": "update_payment",
        "fraud_flag": False,
        "geo_warning": True,
    },

    # --- Card expired — no retry possible, notify only (FR12: 0 retries) ---
    "expired_card": {
        "action": "notify_only",
        "retry_cap": 0,
        "payday_aware": False,
        "geo_block": False,
        "recommended_email": "update_payment",
        "fraud_flag": False,
        "geo_warning": False,
    },
    "card_expired": {  # alternate code used by some issuers
        "action": "notify_only",
        "retry_cap": 0,
        "payday_aware": False,
        "geo_block": False,
        "recommended_email": "update_payment",
        "fraud_flag": False,
        "geo_warning": False,
    },

    # --- Fraud-flagged codes (FR19: stop all actions immediately) ---
    "fraudulent": {
        "action": "fraud_flag",
        "retry_cap": 0,
        "payday_aware": False,
        "geo_block": False,
        "recommended_email": None,
        "fraud_flag": True,
        "geo_warning": False,
    },
    "lost_card": {
        "action": "fraud_flag",
        "retry_cap": 0,
        "payday_aware": False,
        "geo_block": False,
        "recommended_email": None,
        "fraud_flag": True,
        "geo_warning": False,
    },
    "stolen_card": {
        "action": "fraud_flag",
        "retry_cap": 0,
        "payday_aware": False,
        "geo_block": False,
        "recommended_email": None,
        "fraud_flag": True,
        "geo_warning": False,
    },
    "pickup_card": {
        "action": "fraud_flag",
        "retry_cap": 0,
        "payday_aware": False,
        "geo_block": False,
        "recommended_email": None,
        "fraud_flag": True,
        "geo_warning": False,
    },

    # --- 2-retry category (FR12: do_not_honor / generic_decline = 2 retries) ---
    "do_not_honor": {
        "action": "retry_notify",
        "retry_cap": 2,
        "payday_aware": False,
        "geo_block": True,
        "recommended_email": "update_payment",
        "fraud_flag": False,
        "geo_warning": True,
    },
    "generic_decline": {
        "action": "retry_notify",
        "retry_cap": 2,
        "payday_aware": False,
        "geo_block": True,
        "recommended_email": "update_payment",
        "fraud_flag": False,
        "geo_warning": True,
    },

    # --- 1-retry category (FR12: card_velocity_exceeded = 1 retry) ---
    "card_velocity_exceeded": {
        "action": "retry_notify",
        "retry_cap": 1,
        "payday_aware": False,
        "geo_block": False,
        "recommended_email": "update_payment",
        "fraud_flag": False,
        "geo_warning": False,
    },

    # --- Notify-only codes: card update required ---
    "new_account_information_available": {
        "action": "notify_only",
        "retry_cap": 0,
        "payday_aware": False,
        "geo_block": False,
        "recommended_email": "update_payment",
        "fraud_flag": False,
        "geo_warning": False,
    },
    "card_not_supported": {
        "action": "notify_only",
        "retry_cap": 0,
        "payday_aware": False,
        "geo_block": False,
        "recommended_email": "update_payment",
        "fraud_flag": False,
        "geo_warning": False,
    },
    "currency_not_supported": {
        "action": "notify_only",
        "retry_cap": 0,
        "payday_aware": False,
        "geo_block": False,
        "recommended_email": "update_payment",
        "fraud_flag": False,
        "geo_warning": False,
    },
    "service_not_allowed": {
        "action": "notify_only",
        "retry_cap": 0,
        "payday_aware": False,
        "geo_block": False,
        "recommended_email": "update_payment",
        "fraud_flag": False,
        "geo_warning": False,
    },
    "transaction_not_allowed": {
        "action": "notify_only",
        "retry_cap": 0,
        "payday_aware": False,
        "geo_block": False,
        "recommended_email": "update_payment",
        "fraud_flag": False,
        "geo_warning": False,
    },
    "not_permitted": {
        "action": "notify_only",
        "retry_cap": 0,
        "payday_aware": False,
        "geo_block": False,
        "recommended_email": "update_payment",
        "fraud_flag": False,
        "geo_warning": False,
    },
    "restricted_card": {
        "action": "notify_only",
        "retry_cap": 0,
        "payday_aware": False,
        "geo_block": False,
        "recommended_email": "update_payment",
        "fraud_flag": False,
        "geo_warning": False,
    },
    "security_violation": {
        "action": "notify_only",
        "retry_cap": 0,
        "payday_aware": False,
        "geo_block": False,
        "recommended_email": "update_payment",
        "fraud_flag": False,
        "geo_warning": False,
    },
    "stop_payment_order": {
        "action": "notify_only",
        "retry_cap": 0,
        "payday_aware": False,
        "geo_block": False,
        "recommended_email": "update_payment",
        "fraud_flag": False,
        "geo_warning": False,
    },
    "revocation_of_authorization": {
        "action": "notify_only",
        "retry_cap": 0,
        "payday_aware": False,
        "geo_block": False,
        "recommended_email": "update_payment",
        "fraud_flag": False,
        "geo_warning": False,
    },
    "revocation_of_all_authorizations": {
        "action": "notify_only",
        "retry_cap": 0,
        "payday_aware": False,
        "geo_block": False,
        "recommended_email": "update_payment",
        "fraud_flag": False,
        "geo_warning": False,
    },
    "invalid_account": {
        "action": "notify_only",
        "retry_cap": 0,
        "payday_aware": False,
        "geo_block": False,
        "recommended_email": "update_payment",
        "fraud_flag": False,
        "geo_warning": False,
    },

    # --- Retry codes: transient / recoverable ---
    "processing_error": {
        "action": "retry_notify",
        "retry_cap": 1,
        "payday_aware": False,
        "geo_block": False,
        "recommended_email": "update_payment",
        "fraud_flag": False,
        "geo_warning": False,
    },
    "try_again_later": {
        "action": "retry_notify",
        "retry_cap": 1,
        "payday_aware": False,
        "geo_block": False,
        "recommended_email": "update_payment",
        "fraud_flag": False,
        "geo_warning": False,
    },
    "reenter_transaction": {
        "action": "retry_notify",
        "retry_cap": 1,
        "payday_aware": False,
        "geo_block": False,
        "recommended_email": "update_payment",
        "fraud_flag": False,
        "geo_warning": False,
    },
    "no_action_taken": {
        "action": "retry_notify",
        "retry_cap": 1,
        "payday_aware": False,
        "geo_block": False,
        "recommended_email": "update_payment",
        "fraud_flag": False,
        "geo_warning": False,
    },
    "duplicate_transaction": {
        "action": "retry_notify",
        "retry_cap": 1,
        "payday_aware": False,
        "geo_block": False,
        "recommended_email": "update_payment",
        "fraud_flag": False,
        "geo_warning": False,
    },
    "invalid_amount": {
        "action": "retry_notify",
        "retry_cap": 1,
        "payday_aware": False,
        "geo_block": False,
        "recommended_email": "update_payment",
        "fraud_flag": False,
        "geo_warning": False,
    },

    # --- PIN-related: notify only (requires physical interaction) ---
    "incorrect_pin": {
        "action": "notify_only",
        "retry_cap": 0,
        "payday_aware": False,
        "geo_block": False,
        "recommended_email": "update_payment",
        "fraud_flag": False,
        "geo_warning": False,
    },
    "incorrect_cvc": {
        "action": "notify_only",
        "retry_cap": 0,
        "payday_aware": False,
        "geo_block": False,
        "recommended_email": "update_payment",
        "fraud_flag": False,
        "geo_warning": False,
    },
    "pin_try_exceeded": {
        "action": "notify_only",
        "retry_cap": 0,
        "payday_aware": False,
        "geo_block": False,
        "recommended_email": "update_payment",
        "fraud_flag": False,
        "geo_warning": False,
    },
    "offline_pin_required": {
        "action": "notify_only",
        "retry_cap": 0,
        "payday_aware": False,
        "geo_block": False,
        "recommended_email": "update_payment",
        "fraud_flag": False,
        "geo_warning": False,
    },
    "online_or_offline_pin_required": {
        "action": "notify_only",
        "retry_cap": 0,
        "payday_aware": False,
        "geo_block": False,
        "recommended_email": "update_payment",
        "fraud_flag": False,
        "geo_warning": False,
    },

    # --- Catch-all default (FR12: all other codes = 1 retry) ---
    # CRITICAL: Never set action="fraud_flag" here — unknown codes must not auto-flag fraud.
    "_default": {
        "action": "retry_notify",
        "retry_cap": 1,
        "payday_aware": False,
        "geo_block": False,
        "recommended_email": "update_payment",
        "fraud_flag": False,
        "geo_warning": False,
    },
}


def get_rule(decline_code: str | None) -> DeclineRule:
    """
    Look up the rule for a decline code.
    Falls through to _default for any unknown code or None.
    Never raises KeyError.

    Returned dict carries both v0 (action / retry_cap / payday_aware / geo_block)
    and v1 (recommended_email / fraud_flag / geo_warning) keys.
    """
    if not decline_code:
        return dict(DECLINE_RULES["_default"])
    return dict(DECLINE_RULES.get(decline_code.lower().strip(), DECLINE_RULES["_default"]))


def get_recommended_email(
    decline_code: str | None,
    days_since_failure: int,
) -> str:
    """v1 recommended-email mapping (FR10).

    Maps a decline code + age to one of:
        "update_payment", "retry_reminder", "final_notice"  (sendable)
        "fraud_flag", "no_recommendation"                   (UI renders null)

    Day-bucket escalation (only applied when the rule's recommended_email
    is non-None and fraud_flag is False):
        days_since_failure  0–6  → "update_payment"
        days_since_failure  7–13 → "retry_reminder"
        days_since_failure ≥14   → "final_notice"

    Negative days_since_failure (clock skew) is clamped to 0.
    Unknown decline_code falls through to _default — same fallback as get_rule,
    which also lower-cases + strips.
    """
    rule = get_rule(decline_code)
    if rule["fraud_flag"]:
        return "fraud_flag"
    if rule["recommended_email"] is None:
        return "no_recommendation"
    # Architecture line 253: escalation is computed at serialization time, not
    # baked into DECLINE_RULES. The rule's recommended_email field is a
    # "what kind of recommendation does this code support" classifier; the
    # actual returned string for the escalation path is computed from `days`.
    days = max(0, days_since_failure)
    if days <= 6:
        return "update_payment"
    if days <= 13:
        return "retry_reminder"
    return "final_notice"
