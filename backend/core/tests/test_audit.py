import pytest

from core.services.audit import write_audit_event
from core.models.audit import AuditLog


@pytest.mark.django_db
class TestAuditLog:
    def test_write_audit_event_creates_record(self, account):
        write_audit_event(
            subscriber="sub_123",
            actor="engine",
            action="retry_scheduled",
            outcome="success",
            metadata={"decline_code": "insufficient_funds"},
            account=account,
        )
        assert AuditLog.objects.count() == 1
        log = AuditLog.objects.first()
        assert log.actor == "engine"
        assert log.action == "retry_scheduled"
        assert log.outcome == "success"
        assert log.subscriber_id == "sub_123"
        assert log.metadata["decline_code"] == "insufficient_funds"

    def test_audit_log_is_immutable(self, account):
        write_audit_event(None, actor="engine", action="test", outcome="success", account=account)
        log = AuditLog.objects.first()

        with pytest.raises(ValueError, match="immutable"):
            log.outcome = "failed"
            log.save()

    def test_audit_log_has_no_update_admin_permission(self):
        from core.admin import AuditLogAdmin
        from django.contrib.admin.sites import AdminSite
        from unittest.mock import MagicMock

        admin_instance = AuditLogAdmin(AuditLog, AdminSite())
        request = MagicMock()
        assert admin_instance.has_change_permission(request) is False
        assert admin_instance.has_delete_permission(request) is False
        assert admin_instance.has_add_permission(request) is False

    def test_audit_log_without_account(self):
        """Audit events can be written without an account (account-level events)."""
        log = write_audit_event(
            None,
            actor="operator",
            action="system_config_changed",
            outcome="success",
        )
        assert log.account is None
        assert log.pk is not None

    def test_audit_log_timestamp_is_set_automatically(self, account):
        log = write_audit_event(None, actor="client", action="login", outcome="success", account=account)
        assert log.timestamp is not None

    def test_audit_log_metadata_defaults_to_empty_dict(self, account):
        log = write_audit_event(None, actor="engine", action="poll", outcome="skipped", account=account)
        assert log.metadata == {}
