# Story 1.3: Decline-Code Rule Engine Config & Compliance Module

## Status: done

## Story

**As a developer,**
I want the decline-code rule engine defined as a data-driven config with a geo-compliance module,
So that all recovery logic is testable without a database and extensible without touching business logic code.

---

## Acceptance Criteria

**AC1 — DECLINE_RULES config completeness:**
- **Given** the `core/engine/rules.py` module
- **When** I inspect `DECLINE_RULES`
- **Then** it contains entries for 30+ Stripe decline codes, each mapping to `{action, retry_cap, payday_aware, geo_block}`
- **And** the following are explicitly correct:
  - `card_expired` → `{action: "notify_only", retry_cap: 0, payday_aware: False, geo_block: False}`
  - `insufficient_funds` → `{action: "retry_notify", retry_cap: 3, payday_aware: True, geo_block: True}`
  - `fraudulent` → `{action: "fraud_flag", retry_cap: 0, payday_aware: False, geo_block: False}`
  - `do_not_honor` → `{action: "retry_notify", retry_cap: 2, payday_aware: False, geo_block: True}`
  - `card_velocity_exceeded` → `{action: "retry_notify", retry_cap: 1, payday_aware: False, geo_block: False}`
- **And** a `_default` catch-all maps unknown codes to `{action: "retry_notify", retry_cap: 1, payday_aware: False, geo_block: False}` — never fraud-flags

**AC2 — EU/UK compliance module:**
- **Given** `core/engine/compliance.py`
- **When** `is_geo_blocked(payment_method_country, customer_billing_country)` is called with an EU or UK country code
- **Then** it returns `True`, indicating retry must be blocked and routed to notify-only (FR13)
- **And** when called with any non-EU/UK country, returns `False`

**AC3 — Processor: pure Python, correct action resolution:**
- **Given** `core/engine/processor.py`
- **When** `get_recovery_action(decline_code, payment_method_country, customer_billing_country)` is called
- **Then** it returns the correct `action` from `DECLINE_RULES`, overriding to `"notify_only"` if geo-blocked
- **And** the module has zero Django ORM imports — pure Python, no database dependency

**AC4 — Tests pass without database:**
- **Given** the test suite at `backend/core/tests/test_engine/`
- **When** I run `pytest core/tests/test_engine/` (no `--reuse-db`, no DB fixtures)
- **Then** all tests pass with no database connection required
- **And** tests cover: correct action per code, geo-block override, `_default` fallback, fraud flag detection, payday-aware flag, retry cap values

---

## Dev Agent Implementation Guide

### Critical Context

This is **the brain of the entire SafeNet product**. The rule engine determines what happens to every failed payment. It is architecturally isolated as pure Python — zero Django imports — so it can be tested instantly without a database and extracted to a microservice in future.

**The `core/engine/` directory is an `__init__.py` placeholder from Story 1.1.** You are populating it now.

**The `core/tests/test_engine/` directory exists as a placeholder.** You are populating it now.

**Zero Django imports is a hard constraint**, not a guideline. If you import anything from `django.*` anywhere in `core/engine/`, you have violated the architectural contract. Tests will catch this since they run without `@pytest.mark.django_db`.

---

### New Files to Create

```
backend/core/engine/
  rules.py          # DECLINE_RULES config dict — 30+ codes     ← NEW
  processor.py      # get_recovery_action() — applies rule       ← NEW
  compliance.py     # is_geo_blocked() — EU/UK detection         ← NEW
  payday.py         # next_payday_retry_window() — schedule util  ← NEW
  state_machine.py  # FSM constants stub — full impl in Story 3.2 ← NEW

backend/core/tests/test_engine/
  __init__.py                  ← NEW
  test_rules.py                ← NEW
  test_compliance.py           ← NEW
  test_payday.py               ← NEW
  test_processor.py            ← NEW
```

No files from previous stories need to be modified. The engine is a new isolated module.

---

### `core/engine/rules.py` — DECLINE_RULES

```python
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


def get_rule(decline_code: str) -> DeclineRule:
    """
    Look up the rule for a decline code.
    Falls through to _default for any unknown code.
    Never raises KeyError.
    """
    return DECLINE_RULES.get(decline_code, DECLINE_RULES["_default"])
```

---

### `core/engine/compliance.py` — EU/UK Geo-Blocking

```python
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
    payment_method_country: str | None,
    customer_billing_country: str | None,
) -> str:
    """
    Applies compliance override: if geo-blocked, downgrades any retry action to
    "notify_only". Non-retry actions (fraud_flag, notify_only) are unchanged.

    Args:
        rule_action: The action from DECLINE_RULES (e.g. "retry_notify").
        payment_method_country: ISO country code or None.
        customer_billing_country: ISO country code or None.

    Returns:
        Final action string after compliance override.
    """
    if rule_action in ("fraud_flag", "notify_only", "no_action"):
        return rule_action  # compliance does not override non-retry actions

    if is_geo_blocked(payment_method_country, customer_billing_country):
        return "notify_only"

    return rule_action
```

---

### `core/engine/processor.py` — Rule Processor

```python
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

    Example:
        decision = get_recovery_action("insufficient_funds", "US", "US")
        # → RecoveryDecision(action="retry_notify", retry_cap=3, payday_aware=True, geo_blocked=False)

        decision = get_recovery_action("insufficient_funds", "DE", "DE")
        # → RecoveryDecision(action="notify_only", retry_cap=3, payday_aware=True, geo_blocked=True)
    """
    rule = get_rule(decline_code)

    final_action = get_compliant_action(
        rule_action=rule["action"],
        payment_method_country=payment_method_country,
        customer_billing_country=customer_billing_country,
    )

    geo_blocked = (
        rule["geo_block"]
        and final_action != rule["action"]
    )

    return RecoveryDecision(
        decline_code=decline_code,
        action=final_action,
        retry_cap=rule["retry_cap"],
        payday_aware=rule["payday_aware"],
        geo_blocked=geo_blocked,
        rule=rule,
    )
```

---

### `core/engine/payday.py` — Payday Calendar Logic

```python
"""
Payday-aware retry scheduling for insufficient_funds failures.

FR11: SafeNet schedules insufficient_funds retries within a 24-hour window
after the 1st or 15th of the month — payday dates when subscribers are most
likely to have funds available.

NO Django imports. Pure Python.
Uses only stdlib datetime.
"""

from datetime import date, datetime, timedelta, timezone


def next_payday_retry_window(from_date: date) -> tuple[datetime, datetime]:
    """
    Given a reference date, returns the start and end of the next payday retry window.

    Payday dates: 1st and 15th of each month.
    Window: 24 hours starting from midnight UTC on the payday date.

    Rules:
    - If from_date is before the 15th: next window is the 15th of the same month.
    - If from_date is on or after the 15th: next window is the 1st of the next month.
    - If from_date IS a payday (1st or 15th): next window is still in the future
      (use the NEXT payday, not today — failure was detected today, not pre-scheduled).

    Args:
        from_date: The date from which to calculate the next window.
                   Typically: today's date when the failure is detected.

    Returns:
        (window_start, window_end) as UTC-aware datetimes.
        window_end = window_start + 24 hours.

    Examples:
        next_payday_retry_window(date(2026, 4, 1))
        # → (2026-04-15 00:00 UTC, 2026-04-16 00:00 UTC)

        next_payday_retry_window(date(2026, 4, 14))
        # → (2026-04-15 00:00 UTC, 2026-04-16 00:00 UTC)

        next_payday_retry_window(date(2026, 4, 15))
        # → (2026-05-01 00:00 UTC, 2026-05-02 00:00 UTC)

        next_payday_retry_window(date(2026, 4, 30))
        # → (2026-05-01 00:00 UTC, 2026-05-02 00:00 UTC)
    """
    year = from_date.year
    month = from_date.month

    # Is there a 15th window still upcoming this month?
    if from_date.day < 15:
        payday = date(year, month, 15)
    else:
        # Move to 1st of next month
        if month == 12:
            payday = date(year + 1, 1, 1)
        else:
            payday = date(year, month + 1, 1)

    window_start = datetime(payday.year, payday.month, payday.day, 0, 0, 0, tzinfo=timezone.utc)
    window_end = window_start + timedelta(hours=24)
    return window_start, window_end


def is_within_payday_window(dt: datetime) -> bool:
    """
    Returns True if the given datetime falls within a payday retry window.
    Used to determine if an immediate retry is appropriate for payday-aware codes.

    Args:
        dt: UTC-aware datetime to check.

    Returns:
        True if dt is on the 1st or 15th of the month (UTC).
    """
    return dt.day in (1, 15)
```

---

### `core/engine/state_machine.py` — FSM Constants Stub

```python
"""
State machine constants for the 4-state subscriber status machine.
Full FSM transitions implemented in Story 3.2 (django-fsm).

This stub defines the state constants used across the engine to prevent
magic strings and enable IDE autocomplete from Story 1.3 onwards.
"""

# Subscriber status states (FR16)
STATUS_ACTIVE = "active"
STATUS_RECOVERED = "recovered"
STATUS_PASSIVE_CHURN = "passive_churn"
STATUS_FRAUD_FLAGGED = "fraud_flagged"

ALL_STATUSES = (STATUS_ACTIVE, STATUS_RECOVERED, STATUS_PASSIVE_CHURN, STATUS_FRAUD_FLAGGED)

# Actor identifiers (matches AuditLog.actor choices from Story 1.2)
ACTOR_ENGINE = "engine"
ACTOR_OPERATOR = "operator"
ACTOR_CLIENT = "client"

# Recovery action types (matches DECLINE_RULES action values)
ACTION_RETRY_NOTIFY = "retry_notify"
ACTION_NOTIFY_ONLY = "notify_only"
ACTION_FRAUD_FLAG = "fraud_flag"
ACTION_NO_ACTION = "no_action"

ALL_ACTIONS = (ACTION_RETRY_NOTIFY, ACTION_NOTIFY_ONLY, ACTION_FRAUD_FLAG, ACTION_NO_ACTION)
```

---

### Tests

#### `core/tests/test_engine/__init__.py`
```python
# empty
```

#### `core/tests/test_engine/test_rules.py`

```python
"""
Tests for DECLINE_RULES config.
NO database required — pure Python.
Do NOT add @pytest.mark.django_db to any test in this file.
"""
import pytest
from core.engine.rules import DECLINE_RULES, get_rule


class TestDeclineRulesCompleteness:
    def test_has_30_or_more_codes(self):
        # Excludes _default
        real_codes = [k for k in DECLINE_RULES if not k.startswith("_")]
        assert len(real_codes) >= 30

    def test_default_exists(self):
        assert "_default" in DECLINE_RULES

    def test_all_rules_have_required_keys(self):
        required = {"action", "retry_cap", "payday_aware", "geo_block"}
        for code, rule in DECLINE_RULES.items():
            assert required <= set(rule.keys()), f"Rule '{code}' missing keys"

    def test_all_actions_are_valid(self):
        valid_actions = {"retry_notify", "notify_only", "fraud_flag", "no_action"}
        for code, rule in DECLINE_RULES.items():
            assert rule["action"] in valid_actions, f"Rule '{code}' has invalid action: {rule['action']}"

    def test_all_retry_caps_are_non_negative_ints(self):
        for code, rule in DECLINE_RULES.items():
            assert isinstance(rule["retry_cap"], int)
            assert rule["retry_cap"] >= 0


class TestSpecificRules:
    def test_card_expired_is_notify_only_cap_0(self):
        rule = get_rule("card_expired")
        assert rule["action"] == "notify_only"
        assert rule["retry_cap"] == 0

    def test_insufficient_funds_retry_notify_cap_3_payday(self):
        rule = get_rule("insufficient_funds")
        assert rule["action"] == "retry_notify"
        assert rule["retry_cap"] == 3
        assert rule["payday_aware"] is True

    def test_fraudulent_is_fraud_flag_cap_0(self):
        rule = get_rule("fraudulent")
        assert rule["action"] == "fraud_flag"
        assert rule["retry_cap"] == 0

    def test_do_not_honor_retry_notify_cap_2(self):
        rule = get_rule("do_not_honor")
        assert rule["action"] == "retry_notify"
        assert rule["retry_cap"] == 2

    def test_card_velocity_exceeded_retry_notify_cap_1(self):
        rule = get_rule("card_velocity_exceeded")
        assert rule["action"] == "retry_notify"
        assert rule["retry_cap"] == 1

    def test_generic_decline_retry_notify_cap_2(self):
        rule = get_rule("generic_decline")
        assert rule["action"] == "retry_notify"
        assert rule["retry_cap"] == 2

    def test_lost_card_is_fraud_flag(self):
        assert get_rule("lost_card")["action"] == "fraud_flag"

    def test_stolen_card_is_fraud_flag(self):
        assert get_rule("stolen_card")["action"] == "fraud_flag"


class TestDefaultFallback:
    def test_unknown_code_falls_to_default(self):
        rule = get_rule("completely_made_up_code_xyz")
        assert rule == DECLINE_RULES["_default"]

    def test_default_never_fraud_flags(self):
        assert DECLINE_RULES["_default"]["action"] != "fraud_flag"

    def test_default_has_retry_cap_1(self):
        assert DECLINE_RULES["_default"]["retry_cap"] == 1

    def test_empty_string_falls_to_default(self):
        rule = get_rule("")
        assert rule == DECLINE_RULES["_default"]


class TestFraudFlagCodes:
    """Fraud-flagged codes must have retry_cap=0 and action=fraud_flag."""
    fraud_codes = ["fraudulent", "lost_card", "stolen_card", "pickup_card"]

    @pytest.mark.parametrize("code", fraud_codes)
    def test_fraud_code_has_zero_retry_cap(self, code):
        rule = get_rule(code)
        assert rule["action"] == "fraud_flag"
        assert rule["retry_cap"] == 0
```

#### `core/tests/test_engine/test_compliance.py`

```python
"""
Tests for EU/UK geo-blocking compliance module.
NO database required — pure Python.
"""
import pytest
from core.engine.compliance import is_geo_blocked, get_compliant_action, EU_COUNTRY_CODES


class TestIsGeoBlocked:
    @pytest.mark.parametrize("country", ["DE", "FR", "GB", "IT", "ES", "NL", "PL"])
    def test_eu_uk_payment_method_country_is_blocked(self, country):
        assert is_geo_blocked(country, "US") is True

    @pytest.mark.parametrize("country", ["DE", "FR", "GB", "IT", "ES"])
    def test_eu_uk_billing_country_is_blocked(self, country):
        assert is_geo_blocked("US", country) is True

    @pytest.mark.parametrize("country", ["US", "CA", "AU", "JP", "SG", "BR"])
    def test_non_eu_countries_are_not_blocked(self, country):
        assert is_geo_blocked(country, country) is False

    def test_both_none_is_not_blocked(self):
        assert is_geo_blocked(None, None) is False

    def test_payment_method_none_billing_eu_is_blocked(self):
        assert is_geo_blocked(None, "DE") is True

    def test_payment_method_eu_billing_none_is_blocked(self):
        assert is_geo_blocked("FR", None) is True

    def test_case_insensitive(self):
        assert is_geo_blocked("de", "us") is True
        assert is_geo_blocked("DE", "US") is True

    def test_eu_country_codes_has_27_eu_plus_gb(self):
        # 27 EU member states + GB
        assert len(EU_COUNTRY_CODES) >= 28


class TestGetCompliantAction:
    def test_retry_notify_with_eu_billing_becomes_notify_only(self):
        result = get_compliant_action("retry_notify", "US", "DE")
        assert result == "notify_only"

    def test_retry_notify_with_us_billing_unchanged(self):
        result = get_compliant_action("retry_notify", "US", "US")
        assert result == "retry_notify"

    def test_fraud_flag_never_overridden(self):
        result = get_compliant_action("fraud_flag", "DE", "DE")
        assert result == "fraud_flag"

    def test_notify_only_not_changed_by_compliance(self):
        result = get_compliant_action("notify_only", "DE", "DE")
        assert result == "notify_only"

    def test_no_action_not_changed_by_compliance(self):
        result = get_compliant_action("no_action", "DE", "DE")
        assert result == "no_action"
```

#### `core/tests/test_engine/test_payday.py`

```python
"""
Tests for payday calendar scheduling logic.
NO database required — pure Python.
"""
from datetime import date, timezone
from core.engine.payday import next_payday_retry_window, is_within_payday_window


class TestNextPaydayRetryWindow:
    def test_before_15th_returns_15th(self):
        start, end = next_payday_retry_window(date(2026, 4, 1))
        assert start.day == 15
        assert start.month == 4

    def test_on_14th_returns_15th(self):
        start, end = next_payday_retry_window(date(2026, 4, 14))
        assert start.day == 15
        assert start.month == 4

    def test_on_15th_returns_1st_next_month(self):
        start, end = next_payday_retry_window(date(2026, 4, 15))
        assert start.day == 1
        assert start.month == 5

    def test_after_15th_returns_1st_next_month(self):
        start, end = next_payday_retry_window(date(2026, 4, 20))
        assert start.day == 1
        assert start.month == 5

    def test_december_returns_january_1st(self):
        start, end = next_payday_retry_window(date(2026, 12, 16))
        assert start.day == 1
        assert start.month == 1
        assert start.year == 2027

    def test_window_is_24_hours(self):
        start, end = next_payday_retry_window(date(2026, 4, 1))
        delta = end - start
        assert delta.total_seconds() == 24 * 3600

    def test_window_is_utc_aware(self):
        start, end = next_payday_retry_window(date(2026, 4, 1))
        assert start.tzinfo == timezone.utc
        assert end.tzinfo == timezone.utc

    def test_window_starts_at_midnight_utc(self):
        start, _ = next_payday_retry_window(date(2026, 4, 1))
        assert start.hour == 0
        assert start.minute == 0
        assert start.second == 0


class TestIsWithinPaydayWindow:
    def test_1st_is_payday_window(self):
        from datetime import datetime
        dt = datetime(2026, 4, 1, 12, 0, 0, tzinfo=timezone.utc)
        assert is_within_payday_window(dt) is True

    def test_15th_is_payday_window(self):
        from datetime import datetime
        dt = datetime(2026, 4, 15, 6, 0, 0, tzinfo=timezone.utc)
        assert is_within_payday_window(dt) is True

    def test_other_days_are_not_payday_window(self):
        from datetime import datetime
        for day in [2, 10, 14, 16, 28]:
            dt = datetime(2026, 4, day, 0, 0, 0, tzinfo=timezone.utc)
            assert is_within_payday_window(dt) is False, f"Day {day} should not be payday"
```

#### `core/tests/test_engine/test_processor.py`

```python
"""
Tests for the rule engine processor.
NO database required — pure Python.
Verifies end-to-end: decline_code + countries → RecoveryDecision.
"""
from core.engine.processor import get_recovery_action, RecoveryDecision


class TestGetRecoveryAction:
    def test_returns_recovery_decision(self):
        result = get_recovery_action("insufficient_funds")
        assert isinstance(result, RecoveryDecision)

    def test_insufficient_funds_non_eu_gives_retry_notify(self):
        result = get_recovery_action("insufficient_funds", "US", "US")
        assert result.action == "retry_notify"
        assert result.retry_cap == 3
        assert result.payday_aware is True
        assert result.geo_blocked is False

    def test_insufficient_funds_eu_gives_notify_only(self):
        result = get_recovery_action("insufficient_funds", "DE", "DE")
        assert result.action == "notify_only"
        assert result.geo_blocked is True

    def test_card_expired_gives_notify_only(self):
        result = get_recovery_action("card_expired")
        assert result.action == "notify_only"
        assert result.retry_cap == 0

    def test_fraudulent_gives_fraud_flag(self):
        result = get_recovery_action("fraudulent", "US", "US")
        assert result.action == "fraud_flag"
        assert result.retry_cap == 0

    def test_fraudulent_eu_still_fraud_flag(self):
        """Compliance does not downgrade fraud_flag to notify_only."""
        result = get_recovery_action("fraudulent", "DE", "DE")
        assert result.action == "fraud_flag"

    def test_unknown_code_uses_default(self):
        result = get_recovery_action("totally_unknown_xyz")
        assert result.action == "retry_notify"
        assert result.retry_cap == 1
        assert result.geo_blocked is False

    def test_country_none_does_not_crash(self):
        result = get_recovery_action("insufficient_funds", None, None)
        assert result.action == "retry_notify"  # no geo block, both None

    def test_do_not_honor_eu_billing_is_geo_blocked(self):
        result = get_recovery_action("do_not_honor", "US", "FR")
        assert result.action == "notify_only"
        assert result.geo_blocked is True

    def test_do_not_honor_us_is_not_blocked(self):
        result = get_recovery_action("do_not_honor", "US", "US")
        assert result.action == "retry_notify"
        assert result.retry_cap == 2

    def test_decision_is_immutable(self):
        """RecoveryDecision is a frozen dataclass."""
        result = get_recovery_action("card_expired")
        try:
            result.action = "retry_notify"
            assert False, "Should have raised FrozenInstanceError"
        except Exception:
            pass  # expected
```

---

### Verify: Zero Django Imports

After implementing, run this check to confirm engine isolation:

```bash
# Should produce no output (zero Django imports in engine/)
grep -r "from django" backend/core/engine/
grep -r "import django" backend/core/engine/
```

If either command produces output, the architectural contract is violated.

---

### pytest.ini Note

Engine tests run **without** `@pytest.mark.django_db`. The `pytest.ini` from Story 1.1 sets `DJANGO_SETTINGS_MODULE` — this is fine, Django can be configured without hitting the DB. To explicitly confirm tests don't need DB:

```bash
# Should pass with or without --no-db flag
cd backend && pytest core/tests/test_engine/ -v
```

No `db` fixtures, no `django_db` markers, no model imports anywhere in the engine test files.

---

### What NOT to implement in Story 1.3

- No `Subscriber` or `SubscriberFailure` ORM models → Story 3.2
- No actual Celery polling or retry tasks → Stories 2.2, 3.2
- No FSM state transitions (full `django-fsm` integration) → Story 3.2
- `state_machine.py` constants stub only — no `TRANSITION` decorators
- No notification dispatch → Epic 4
- No database reads/writes in any engine module

---

## Previous Story Intelligence

**Story 1.1 debug notes carried forward:**
- Celery tests use `task_always_eager=True` — engine tests don't use Celery at all, no fixture needed
- Package versions confirmed working; `cryptography` is already installed (used by Story 1.2)

**Story 1.2 patterns to follow:**
- `write_audit_event()` helper established — when processor decisions are acted on (in later stories), always use this, not inline `AuditLog.objects.create()`
- `TenantScopedModel` established — the `Subscriber` model in Story 3.2 will use it; processor.py returns a `RecoveryDecision` that the task layer maps to model operations
- The processor deliberately receives plain values (strings), not ORM objects — this is intentional. Tasks (Story 3.2) bridge ORM ↔ engine.

**Architecture dependency chain context:**
```
Story 1.3 (engine config) → Story 3.2 (FSM + Subscriber model using engine)
                          → Story 2.2 (polling task calls processor)
                          → Story 3.3 (card update immediate retry uses processor)
```

---

## Critical Anti-Patterns to Prevent

| Anti-pattern | Why forbidden |
|---|---|
| `from django.db import models` in `core/engine/` | Breaks architectural isolation; engine must be DB-free |
| `from core.models import ...` in `core/engine/` | Same violation — models are Django ORM |
| `get_rule("fraudulent")["action"] == "fraud_flag"` check skipped | Fraud flagging must be explicit and tested |
| Setting `"_default": {"action": "fraud_flag", ...}` | Unknown codes must never auto-flag fraud |
| `geo_block: True` on codes that aren't retry-based | geo_block only matters for retry actions; fraud_flag ignores it |
| Hardcoding country lists inline in tasks | EU_COUNTRY_CODES lives in compliance.py — single source of truth |

---

## Review Findings

- [x] [Review][Decision] `geo_blocked` flag is `False` even when compliance overrides action for rules with `geo_block=False` — Fixed: `get_compliant_action` now respects `geo_block` flag, `geo_blocked` reflects actual override
- [x] [Review][Decision] `get_rule` does not normalize decline_code (case/whitespace) — Fixed: added `.lower().strip()` normalization in `get_rule`
- [x] [Review][Patch] `DECLINE_RULES` values are mutable — Fixed: `get_rule()` now returns a copy
- [x] [Review][Patch] `test_decision_is_immutable` uses bare `except Exception` — Fixed: uses `pytest.raises(AttributeError)`
- [x] [Review][Defer] `is_within_payday_window` timezone handling inconsistent with `next_payday_retry_window` [payday.py:62-65] — deferred, not used in production yet (Story 3.2)
- [x] [Review][Defer] `get_compliant_action` allowlist may not cover future action types [compliance.py:88] — deferred, action set is fixed by current spec

## Out of Scope

- Subscriber / SubscriberFailure ORM models (Story 3.2)
- Celery polling and retry task implementation (Stories 2.2, 3.2)
- Full FSM state transitions with `django-fsm` (Story 3.2)
- Email notification dispatch (Epic 4)
- Dashboard UI (later epics)
