"""
Tests for DECLINE_RULES config.
NO database required — pure Python.
Do NOT add @pytest.mark.django_db to any test in this file.
"""
import pytest
from core.engine.rules import DECLINE_RULES, get_recommended_email, get_rule


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


class TestDeclineRulesV1Schema:
    """Story 3.5 v1: every rule entry exposes recommended_email/fraud_flag/geo_warning."""

    def test_all_rules_have_v1_keys(self):
        v1_required = {"recommended_email", "fraud_flag", "geo_warning"}
        for code, rule in DECLINE_RULES.items():
            assert v1_required <= set(rule.keys()), f"Rule '{code}' missing v1 keys"
            assert rule["recommended_email"] in {
                "update_payment",
                "retry_reminder",
                "final_notice",
                None,
            }, f"Rule '{code}' has invalid recommended_email"
            assert isinstance(rule["fraud_flag"], bool)
            assert isinstance(rule["geo_warning"], bool)

    def test_fraud_codes_have_no_recommendation(self):
        for code in ("fraudulent", "lost_card", "stolen_card", "pickup_card"):
            assert DECLINE_RULES[code]["fraud_flag"] is True
            assert DECLINE_RULES[code]["recommended_email"] is None

    def test_default_recommends_update_payment(self):
        assert DECLINE_RULES["_default"]["recommended_email"] == "update_payment"
        assert DECLINE_RULES["_default"]["fraud_flag"] is False
        assert DECLINE_RULES["_default"]["geo_warning"] is False

    def test_eu_warning_codes(self):
        # insufficient_funds + the two generic decline codes carry geo_warning.
        for code in ("insufficient_funds", "do_not_honor", "generic_decline"):
            assert DECLINE_RULES[code]["geo_warning"] is True

    def test_v0_keys_unchanged(self):
        # Spot-check a handful of v0 values to guard against drift in the
        # quarantine-branch reactivation contract.
        assert DECLINE_RULES["insufficient_funds"]["action"] == "retry_notify"
        assert DECLINE_RULES["insufficient_funds"]["retry_cap"] == 3
        assert DECLINE_RULES["insufficient_funds"]["payday_aware"] is True
        assert DECLINE_RULES["insufficient_funds"]["geo_block"] is True
        assert DECLINE_RULES["fraudulent"]["action"] == "fraud_flag"
        assert DECLINE_RULES["_default"]["retry_cap"] == 1


class TestGetRecommendedEmail:
    """Story 3.5 v1 (FR10): decline_code + days_since_failure → recommended email."""

    @pytest.mark.parametrize(
        "days,expected",
        [
            (0, "update_payment"),
            (1, "update_payment"),
            (6, "update_payment"),     # upper bound of update_payment bucket
            (7, "retry_reminder"),     # lower bound of retry_reminder bucket
            (10, "retry_reminder"),
            (13, "retry_reminder"),    # upper bound of retry_reminder bucket
            (14, "final_notice"),      # lower bound of final_notice bucket
            (365, "final_notice"),     # arbitrary far-future
            (-3, "update_payment"),    # negative clamps to 0 (clock skew)
            (-1000, "update_payment"),
        ],
    )
    def test_day_bucket_escalation_for_default_rule(self, days, expected):
        assert get_recommended_email("insufficient_funds", days) == expected

    @pytest.mark.parametrize("code", ["fraudulent", "lost_card", "stolen_card", "pickup_card"])
    @pytest.mark.parametrize("days", [0, 6, 7, 13, 14, 365])
    def test_fraud_codes_always_return_fraud_flag(self, code, days):
        assert get_recommended_email(code, days) == "fraud_flag"

    def test_unknown_code_falls_through_to_default_and_follows_bucket(self):
        # _default has recommended_email="update_payment", fraud_flag=False.
        assert get_recommended_email("totally_made_up", 0) == "update_payment"
        assert get_recommended_email("totally_made_up", 8) == "retry_reminder"
        assert get_recommended_email("totally_made_up", 30) == "final_notice"

    def test_none_decline_code_falls_through_to_default(self):
        assert get_recommended_email(None, 0) == "update_payment"
        assert get_recommended_email(None, 14) == "final_notice"

    def test_empty_string_decline_code_falls_through_to_default(self):
        assert get_recommended_email("", 0) == "update_payment"
        assert get_recommended_email("", 20) == "final_notice"

    def test_decline_code_is_lowercased_and_stripped(self):
        # Parity with get_rule's normalization.
        assert get_recommended_email("  INSUFFICIENT_FUNDS  ", 5) == "update_payment"
        assert get_recommended_email("Insufficient_Funds", 8) == "retry_reminder"
        assert get_recommended_email("FRAUDULENT", 0) == "fraud_flag"

    def test_no_recommendation_branch_via_synthetic_rule(self, monkeypatch):
        # No real code in v1 has recommended_email=None AND fraud_flag=False,
        # but the branch must exist for forward-compatibility. Drive it by
        # monkeypatching get_rule to return a synthetic rule.
        from core.engine import rules as rules_module

        synthetic = {
            "action": "no_action",
            "retry_cap": 0,
            "payday_aware": False,
            "geo_block": False,
            "recommended_email": None,
            "fraud_flag": False,
            "geo_warning": False,
        }
        monkeypatch.setattr(rules_module, "get_rule", lambda _code: synthetic)
        # days value irrelevant — the no_recommendation branch fires before bucket logic.
        assert rules_module.get_recommended_email("anything", 0) == "no_recommendation"
        assert rules_module.get_recommended_email("anything", 100) == "no_recommendation"

    def test_return_value_is_always_in_closed_vocabulary(self, monkeypatch):
        # AC1 (FR10): the public return set is exactly five strings. Defends
        # against silent vocabulary drift (a future rule introducing a new
        # return path or a typo in a string literal).
        allowed = {
            "update_payment",
            "retry_reminder",
            "final_notice",
            "fraud_flag",
            "no_recommendation",
        }
        sample_codes = [
            "insufficient_funds",   # update_payment / retry_reminder / final_notice
            "fraudulent",           # fraud_flag
            "totally_made_up",      # _default fallback
            None,                   # _default via None
            "",                     # _default via empty
        ]
        for code in sample_codes:
            for days in (-5, 0, 6, 7, 13, 14, 365):
                assert get_recommended_email(code, days) in allowed

        # Drive the no_recommendation branch synthetically.
        from core.engine import rules as rules_module
        synthetic = {
            "action": "no_action",
            "retry_cap": 0,
            "payday_aware": False,
            "geo_block": False,
            "recommended_email": None,
            "fraud_flag": False,
            "geo_warning": False,
        }
        monkeypatch.setattr(rules_module, "get_rule", lambda _code: synthetic)
        assert rules_module.get_recommended_email("x", 0) in allowed
