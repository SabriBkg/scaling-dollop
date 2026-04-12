"""Tests for the trial expiration Celery task."""
import pytest
from datetime import timedelta
from django.utils import timezone

from core.models.account import TIER_FREE, TIER_MID
from core.models.audit import AuditLog


@pytest.mark.django_db
class TestExpireTrials:
    def test_expires_overdue_trial(self, account):
        """Accounts past trial_ends_at are downgraded to Free."""
        account.tier = TIER_MID
        account.trial_ends_at = timezone.now() - timedelta(days=1)
        account.save()

        from core.tasks.trial_expiration import expire_trials
        result = expire_trials()

        account.refresh_from_db()
        assert account.tier == TIER_FREE
        assert result["expired_count"] == 1

    def test_does_not_expire_active_trial(self, account):
        """Accounts still in trial period are not downgraded."""
        account.tier = TIER_MID
        account.trial_ends_at = timezone.now() + timedelta(days=10)
        account.save()

        from core.tasks.trial_expiration import expire_trials
        result = expire_trials()

        account.refresh_from_db()
        assert account.tier == TIER_MID
        assert result["expired_count"] == 0

    def test_writes_audit_event(self, account):
        """Expiration writes a trial_expired audit event."""
        account.tier = TIER_MID
        account.trial_ends_at = timezone.now() - timedelta(days=1)
        account.save()

        from core.tasks.trial_expiration import expire_trials
        expire_trials()

        audit = AuditLog.objects.filter(action="trial_expired", account=account).first()
        assert audit is not None
        assert audit.outcome == "success"

    def test_skips_free_tier(self, account):
        """Free-tier accounts are not affected."""
        account.tier = TIER_FREE
        account.trial_ends_at = None
        account.save()

        from core.tasks.trial_expiration import expire_trials
        result = expire_trials()
        assert result["expired_count"] == 0

    def test_skips_paid_mid(self, account):
        """Paid Mid accounts (no trial_ends_at) are not downgraded."""
        account.tier = TIER_MID
        account.trial_ends_at = None
        account.save()

        from core.tasks.trial_expiration import expire_trials
        result = expire_trials()

        account.refresh_from_db()
        assert account.tier == TIER_MID
        assert result["expired_count"] == 0
