import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from core.models.account import Account
from core.models.audit import AuditLog


@pytest.mark.django_db
class TestSetEngineMode:
    URL = "/api/v1/account/engine/mode/"

    @pytest.fixture
    def mid_account_with_dpa(self, account):
        account.tier = "mid"
        account.dpa_accepted_at = timezone.now()
        account.save()
        return account

    def test_first_activation_autopilot(self, auth_client, mid_account_with_dpa):
        response = auth_client.post(self.URL, {"mode": "autopilot"}, format="json")
        assert response.status_code == 200

        data = response.json()["data"]
        assert data["engine_mode"] == "autopilot"
        assert data["engine_active"] is True

        log = AuditLog.objects.filter(action="engine_activated").first()
        assert log is not None
        assert log.metadata == {"mode": "autopilot"}

    def test_first_activation_supervised(self, auth_client, mid_account_with_dpa):
        response = auth_client.post(self.URL, {"mode": "supervised"}, format="json")
        assert response.status_code == 200

        data = response.json()["data"]
        assert data["engine_mode"] == "supervised"

        log = AuditLog.objects.filter(action="engine_activated").first()
        assert log is not None
        assert log.metadata == {"mode": "supervised"}

    def test_mode_switch_creates_switch_audit(self, auth_client, mid_account_with_dpa):
        mid_account_with_dpa.engine_mode = "autopilot"
        mid_account_with_dpa.save()

        response = auth_client.post(self.URL, {"mode": "supervised"}, format="json")
        assert response.status_code == 200

        data = response.json()["data"]
        assert data["engine_mode"] == "supervised"

        log = AuditLog.objects.filter(action="engine_mode_switched").first()
        assert log is not None
        assert log.metadata == {"from": "autopilot", "to": "supervised"}

    def test_same_mode_idempotent(self, auth_client, mid_account_with_dpa):
        mid_account_with_dpa.engine_mode = "autopilot"
        mid_account_with_dpa.save()

        response = auth_client.post(self.URL, {"mode": "autopilot"}, format="json")
        assert response.status_code == 200

        assert AuditLog.objects.filter(action="engine_activated").count() == 0
        assert AuditLog.objects.filter(action="engine_mode_switched").count() == 0

    def test_rejected_without_dpa(self, auth_client, account):
        account.tier = "mid"
        account.save()

        response = auth_client.post(self.URL, {"mode": "autopilot"}, format="json")
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "DPA_NOT_ACCEPTED"

    def test_rejected_for_free_tier(self, auth_client, account):
        account.tier = "free"
        account.dpa_accepted_at = timezone.now()
        account.save()

        response = auth_client.post(self.URL, {"mode": "autopilot"}, format="json")
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "TIER_NOT_ELIGIBLE"

    def test_invalid_mode_rejected(self, auth_client, mid_account_with_dpa):
        response = auth_client.post(self.URL, {"mode": "invalid"}, format="json")
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "INVALID_MODE"

    def test_missing_mode_rejected(self, auth_client, mid_account_with_dpa):
        response = auth_client.post(self.URL, {}, format="json")
        assert response.status_code == 400

    def test_requires_authentication(self, db):
        client = APIClient()
        response = client.post(self.URL, {"mode": "autopilot"}, format="json")
        assert response.status_code == 401

    def test_response_includes_all_account_fields(self, auth_client, mid_account_with_dpa):
        response = auth_client.post(self.URL, {"mode": "autopilot"}, format="json")
        data = response.json()["data"]

        assert "id" in data
        assert "owner" in data
        assert "tier" in data
        assert "dpa_accepted" in data
        assert "engine_mode" in data
        assert "engine_active" in data
