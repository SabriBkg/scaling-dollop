"""
Rule engine processor — applies DECLINE_RULES to a payment failure.

Entry point for all recovery logic. Called by tasks/polling.py for every
new failure event detected.

NO Django imports. Pure Python.
The processor knows nothing about ORM models — it works with plain values.
The calling task (tasks/polling.py) is responsible for loading/saving models.
"""

from dataclasses import dataclass

from core.engine.rules import get_rule, DeclineRule
from core.engine.compliance import get_compliant_action


@dataclass(frozen=True)
class RecoveryDecision:
    """
    The engine's verdict for a single payment failure.
    Immutable value object — safe to pass across task boundaries.
    """
    decline_code: str
    action: str           # final action after compliance override
    retry_cap: int
    payday_aware: bool
    geo_blocked: bool     # True if compliance override was applied
    rule: DeclineRule     # the raw rule before override (for audit metadata)


def get_recovery_action(
    decline_code: str,
    payment_method_country: str | None = None,
    customer_billing_country: str | None = None,
) -> RecoveryDecision:
    """
    Determines the correct recovery action for a failed payment.

    Steps:
    1. Look up decline code in DECLINE_RULES (falls back to _default for unknowns).
    2. Apply EU/UK compliance override if applicable.
    3. Return a RecoveryDecision with the final action and all metadata.

    Args:
        decline_code: Stripe decline code string (e.g. "insufficient_funds").
        payment_method_country: ISO 3166-1 alpha-2 of the payment method. May be None.
        customer_billing_country: ISO 3166-1 alpha-2 of billing address. May be None.

    Returns:
        RecoveryDecision with final action.
    """
    rule = get_rule(decline_code)

    final_action = get_compliant_action(
        rule_action=rule["action"],
        geo_block=rule["geo_block"],
        payment_method_country=payment_method_country,
        customer_billing_country=customer_billing_country,
    )

    geo_blocked = final_action != rule["action"]

    return RecoveryDecision(
        decline_code=decline_code,
        action=final_action,
        retry_cap=rule["retry_cap"],
        payday_aware=rule["payday_aware"],
        geo_blocked=geo_blocked,
        rule=rule,
    )
