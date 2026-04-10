"""
Tests for the rule engine processor.
NO database required — pure Python.
Verifies end-to-end: decline_code + countries → RecoveryDecision.
"""
import pytest
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
        with pytest.raises(AttributeError):
            result.action = "retry_notify"
