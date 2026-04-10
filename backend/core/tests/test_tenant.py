import pytest
from django.contrib.auth.models import User

from core.models.account import Account


@pytest.mark.django_db
class TestTenantIsolation:
    def test_account_auto_created_on_user_creation(self, user):
        assert hasattr(user, "account")
        assert isinstance(user.account, Account)

    def test_account_owner_is_user(self, user, account):
        assert account.owner == user

    def test_two_users_have_separate_accounts(self, db):
        user1 = User.objects.create_user(username="u1", email="u1@test.com", password="pass")
        user2 = User.objects.create_user(username="u2", email="u2@test.com", password="pass")
        assert user1.account != user2.account
        assert user1.account.id != user2.account.id

    def test_for_account_only_returns_own_records(self, db):
        """for_account() must not leak records across tenants."""
        from core.models.audit import AuditLog
        from core.services.audit import write_audit_event

        user1 = User.objects.create_user(username="tenant1", email="t1@test.com", password="pass")
        user2 = User.objects.create_user(username="tenant2", email="t2@test.com", password="pass")

        write_audit_event(None, actor="engine", action="test_event", outcome="success", account=user1.account)
        write_audit_event(None, actor="engine", action="test_event", outcome="success", account=user2.account)

        account1_logs = AuditLog.objects.for_account(user1.account.id)
        account2_logs = AuditLog.objects.for_account(user2.account.id)

        assert account1_logs.count() == 1
        assert account2_logs.count() == 1
        assert account1_logs.first().account == user1.account
        assert account2_logs.first().account == user2.account
