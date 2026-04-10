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
