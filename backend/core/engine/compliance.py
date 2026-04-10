"""
EU/UK compliance module — geo-aware retry blocking.

FR13: SafeNet detects EU/UK payment contexts (identified via Stripe payment method
country OR customer billing address country) and routes them to notify-only, blocking
automated retries.

GDPR and EU payment retry regulations prohibit automated retries without explicit
customer authorisation in EU/UK jurisdictions. SafeNet routes these to notify-only
regardless of the decline code rule.

No Django imports. Pure Python.
"""

# ISO 3166-1 alpha-2 country codes for EU member states + UK
EU_COUNTRY_CODES: frozenset[str] = frozenset({
    "AT",  # Austria
    "BE",  # Belgium
    "BG",  # Bulgaria
    "CY",  # Cyprus
    "CZ",  # Czech Republic
    "DE",  # Germany
    "DK",  # Denmark
    "EE",  # Estonia
    "ES",  # Spain
    "FI",  # Finland
    "FR",  # France
    "GB",  # United Kingdom (post-Brexit but same regulatory framework for payments)
    "GR",  # Greece
    "HR",  # Croatia
    "HU",  # Hungary
    "IE",  # Ireland
    "IT",  # Italy
    "LT",  # Lithuania
    "LU",  # Luxembourg
    "LV",  # Latvia
    "MT",  # Malta
    "NL",  # Netherlands
    "PL",  # Poland
    "PT",  # Portugal
    "RO",  # Romania
    "SE",  # Sweden
    "SI",  # Slovenia
    "SK",  # Slovakia
})


def is_geo_blocked(
    payment_method_country: str | None,
    customer_billing_country: str | None,
) -> bool:
    """
    Returns True if this payment context is EU/UK, meaning automated retries
    must be blocked and the action overridden to "notify_only".

    FR13: blocked if EITHER payment_method_country OR customer_billing_country is EU/UK.
    Unknown/None countries are treated as non-EU (conservative — do not block unnecessarily).

    Args:
        payment_method_country: ISO 3166-1 alpha-2 (e.g. "DE", "US"). May be None.
        customer_billing_country: ISO 3166-1 alpha-2. May be None.

    Returns:
        True if retry should be blocked (EU/UK context detected).
    """
    pm_country = (payment_method_country or "").upper().strip()
    billing_country = (customer_billing_country or "").upper().strip()

    return pm_country in EU_COUNTRY_CODES or billing_country in EU_COUNTRY_CODES


def get_compliant_action(
    rule_action: str,
    geo_block: bool,
    payment_method_country: str | None,
    customer_billing_country: str | None,
) -> str:
    """
    Applies compliance override: if the rule is geo-block-eligible and the
    payment context is EU/UK, downgrades the action to "notify_only".

    Args:
        rule_action: The action from DECLINE_RULES (e.g. "retry_notify").
        geo_block: The rule's geo_block flag — True if this code is subject to EU/UK override.
        payment_method_country: ISO country code or None.
        customer_billing_country: ISO country code or None.

    Returns:
        Final action string after compliance override.
    """
    if not geo_block:
        return rule_action

    if is_geo_blocked(payment_method_country, customer_billing_country):
        return "notify_only"

    return rule_action
