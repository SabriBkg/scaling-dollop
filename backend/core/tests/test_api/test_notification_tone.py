"""Tests for the notification-tone update endpoint."""
import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from core.models.audit import AuditLog


@pytest.mark.django_db
class TestSetNotificationTone:
    URL = "/api/v1/account/notification-tone/"

    @pytest.fixture
    def mid_account(self, account):
        account.tier = "mid"
        account.dpa_accepted_at = timezone.now()
        account.engine_mode = "autopilot"
        account.save()
        return account

    def test_change_from_professional_to_friendly(self, auth_client, mid_account):
        # Default seeded value is "professional"; change to "friendly".
        response = auth_client.post(self.URL, {"tone": "friendly"}, format="json")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["notification_tone"] == "friendly"

        log = AuditLog.objects.filter(action="notification_tone_changed").first()
        assert log is not None
        assert log.metadata == {"from": "professional", "to": "friendly"}

    def test_change_to_minimal(self, auth_client, mid_account):
        response = auth_client.post(self.URL, {"tone": "minimal"}, format="json")
        assert response.status_code == 200
        assert response.json()["data"]["notification_tone"] == "minimal"

    def test_idempotent_when_unchanged(self, auth_client, mid_account):
        # Account already has notification_tone="professional" (default).
        # Spec requires idempotency: no audit row AND no DB write on a no-op.
        from unittest.mock import patch

        with patch("core.models.account.Account.save") as mock_save:
            response = auth_client.post(self.URL, {"tone": "professional"}, format="json")
        assert response.status_code == 200
        assert AuditLog.objects.filter(action="notification_tone_changed").count() == 0
        assert mock_save.call_count == 0

    def test_invalid_tone_rejected(self, auth_client, mid_account):
        response = auth_client.post(self.URL, {"tone": "shouting"}, format="json")
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "INVALID_TONE"

    def test_missing_tone_rejected(self, auth_client, mid_account):
        response = auth_client.post(self.URL, {}, format="json")
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "INVALID_TONE"

    def test_rejected_for_free_tier(self, auth_client, account):
        account.tier = "free"
        account.save()

        response = auth_client.post(self.URL, {"tone": "friendly"}, format="json")
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "TIER_NOT_ELIGIBLE"

    def test_rejected_when_dpa_not_accepted(self, auth_client, account):
        account.tier = "mid"
        account.engine_mode = "autopilot"
        account.dpa_accepted_at = None
        account.save()

        response = auth_client.post(self.URL, {"tone": "friendly"}, format="json")
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "DPA_NOT_ACCEPTED"

    def test_rejected_when_engine_mode_not_set(self, auth_client, account):
        account.tier = "mid"
        account.dpa_accepted_at = timezone.now()
        account.engine_mode = None
        account.save()

        response = auth_client.post(self.URL, {"tone": "friendly"}, format="json")
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "ENGINE_MODE_NOT_SET"

    def test_requires_authentication(self, db):
        client = APIClient()
        response = client.post(self.URL, {"tone": "friendly"}, format="json")
        assert response.status_code == 401

    def test_response_envelope_includes_account_fields(self, auth_client, mid_account):
        response = auth_client.post(self.URL, {"tone": "friendly"}, format="json")
        data = response.json()["data"]
        assert "id" in data
        assert "tier" in data
        assert "notification_tone" in data
        assert "engine_mode" in data
