import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.models.account import Account
from core.models.audit import AuditLog


@pytest.mark.django_db
class TestAcceptDpa:
    URL = "/api/v1/account/dpa/accept/"

    def test_accept_dpa_success(self, auth_client, account):
        account.tier = "mid"
        account.save()

        response = auth_client.post(self.URL, format="json")
        assert response.status_code == 200

        data = response.json()["data"]
        assert data["dpa_accepted"] is True
        assert data["dpa_accepted_at"] is not None

        account.refresh_from_db()
        assert account.dpa_accepted_at is not None

    def test_accept_dpa_creates_audit_event(self, auth_client, account):
        account.tier = "mid"
        account.save()

        auth_client.post(self.URL, format="json")

        log = AuditLog.objects.filter(action="dpa_accepted").first()
        assert log is not None
        assert log.actor == "client"
        assert log.outcome == "success"
        assert log.account == account

    def test_accept_dpa_idempotent(self, auth_client, account):
        account.tier = "mid"
        account.dpa_accepted_at = timezone.now()
        account.save()
        original_ts = account.dpa_accepted_at

        response = auth_client.post(self.URL, format="json")
        assert response.status_code == 200

        account.refresh_from_db()
        assert account.dpa_accepted_at == original_ts
        # No duplicate audit event
        assert AuditLog.objects.filter(action="dpa_accepted").count() == 0

    def test_accept_dpa_rejected_for_free_tier(self, auth_client, account):
        account.tier = "free"
        account.save()

        response = auth_client.post(self.URL, format="json")
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "TIER_NOT_ELIGIBLE"

    def test_accept_dpa_pro_tier_allowed(self, auth_client, account):
        account.tier = "pro"
        account.save()

        response = auth_client.post(self.URL, format="json")
        assert response.status_code == 200
        assert response.json()["data"]["dpa_accepted"] is True

    def test_accept_dpa_requires_authentication(self, db):
        client = APIClient()
        response = client.post(self.URL, format="json")
        assert response.status_code == 401

    def test_response_includes_all_account_fields(self, auth_client, account):
        account.tier = "mid"
        account.save()

        response = auth_client.post(self.URL, format="json")
        data = response.json()["data"]

        assert "id" in data
        assert "owner" in data
        assert "tier" in data
        assert "dpa_accepted" in data
        assert "dpa_accepted_at" in data
        assert "engine_mode" in data
        assert "engine_active" in data
        assert "profile_complete" in data
