"""Tests for the tier gating service."""
import pytest
from datetime import timedelta
from django.utils import timezone

from core.models.account import Account, TIER_FREE, TIER_MID, TIER_PRO


@pytest.mark.django_db
class TestGetPollingFrequency:
    def test_mid_tier_returns_hourly(self, account):
        account.tier = TIER_MID
        account.save()
        from core.services.tier import get_polling_frequency
        assert get_polling_frequency(account) == 3600

    def test_pro_tier_returns_hourly(self, account):
        account.tier = TIER_PRO
        account.save()
        from core.services.tier import get_polling_frequency
        assert get_polling_frequency(account) == 3600

    def test_free_tier_returns_fifteen_days(self, account):
        account.tier = TIER_FREE
        account.save()
        from core.services.tier import get_polling_frequency
        assert get_polling_frequency(account) == 1_296_000


@pytest.mark.django_db
class TestIsEngineActive:
    def test_mid_tier_active_with_dpa_and_mode(self, account):
        account.tier = TIER_MID
        account.dpa_accepted_at = timezone.now()
        account.engine_mode = "autopilot"
        account.save()
        from core.services.tier import is_engine_active
        assert is_engine_active(account) is True

    def test_pro_tier_active_with_dpa_and_mode(self, account):
        account.tier = TIER_PRO
        account.dpa_accepted_at = timezone.now()
        account.engine_mode = "supervised"
        account.save()
        from core.services.tier import is_engine_active
        assert is_engine_active(account) is True

    def test_mid_tier_inactive_without_dpa(self, account):
        account.tier = TIER_MID
        account.save()
        from core.services.tier import is_engine_active
        assert is_engine_active(account) is False

    def test_mid_tier_inactive_without_mode(self, account):
        account.tier = TIER_MID
        account.dpa_accepted_at = timezone.now()
        account.save()
        from core.services.tier import is_engine_active
        assert is_engine_active(account) is False

    def test_free_tier_inactive(self, account):
        account.tier = TIER_FREE
        account.save()
        from core.services.tier import is_engine_active
        assert is_engine_active(account) is False


@pytest.mark.django_db
class TestCheckAndDegradeTrial:
    def test_degrades_expired_trial(self, account):
        account.tier = TIER_MID
        account.trial_ends_at = timezone.now() - timedelta(days=1)
        account.save()
        from core.services.tier import check_and_degrade_trial
        assert check_and_degrade_trial(account) is True
        account.refresh_from_db()
        assert account.tier == TIER_FREE

    def test_no_degrade_active_trial(self, account):
        account.tier = TIER_MID
        account.trial_ends_at = timezone.now() + timedelta(days=10)
        account.save()
        from core.services.tier import check_and_degrade_trial
        assert check_and_degrade_trial(account) is False
        account.refresh_from_db()
        assert account.tier == TIER_MID

    def test_no_degrade_free_tier(self, account):
        account.tier = TIER_FREE
        account.trial_ends_at = None
        account.save()
        from core.services.tier import check_and_degrade_trial
        assert check_and_degrade_trial(account) is False

    def test_no_degrade_paid_mid(self, account):
        """Mid tier with no trial_ends_at (paid subscriber) should not degrade."""
        account.tier = TIER_MID
        account.trial_ends_at = None
        account.save()
        from core.services.tier import check_and_degrade_trial
        assert check_and_degrade_trial(account) is False
        account.refresh_from_db()
        assert account.tier == TIER_MID


@pytest.mark.django_db
class TestUpgradeToMid:
    def test_upgrades_free_to_mid(self, account):
        account.tier = TIER_FREE
        account.trial_ends_at = timezone.now() - timedelta(days=30)
        account.save()
        from core.services.tier import upgrade_to_mid
        upgrade_to_mid(account)
        account.refresh_from_db()
        assert account.tier == TIER_MID
        assert account.trial_ends_at is None
