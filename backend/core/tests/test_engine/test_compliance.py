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
    def test_retry_notify_geo_block_eu_becomes_notify_only(self):
        result = get_compliant_action("retry_notify", True, "US", "DE")
        assert result == "notify_only"

    def test_retry_notify_geo_block_us_unchanged(self):
        result = get_compliant_action("retry_notify", True, "US", "US")
        assert result == "retry_notify"

    def test_retry_notify_no_geo_block_eu_unchanged(self):
        result = get_compliant_action("retry_notify", False, "DE", "DE")
        assert result == "retry_notify"

    def test_fraud_flag_geo_block_false_unchanged(self):
        result = get_compliant_action("fraud_flag", False, "DE", "DE")
        assert result == "fraud_flag"

    def test_notify_only_geo_block_true_unchanged(self):
        result = get_compliant_action("notify_only", True, "DE", "DE")
        assert result == "notify_only"

    def test_no_action_geo_block_false_unchanged(self):
        result = get_compliant_action("no_action", False, "DE", "DE")
        assert result == "no_action"
