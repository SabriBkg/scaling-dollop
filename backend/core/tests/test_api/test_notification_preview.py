"""Tests for the live notification preview endpoint."""
import pytest
from django.utils import timezone
from rest_framework.test import APIClient


@pytest.mark.django_db
class TestNotificationPreview:
    URL = "/api/v1/account/notification-preview/"

    def test_happy_path_returns_subject_and_html(self, auth_client, account):
        account.tier = "mid"
        account.dpa_accepted_at = timezone.now()
        account.company_name = "Acme Corp"
        account.save()

        response = auth_client.get(f"{self.URL}?tone=professional")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["tone"] == "professional"
        assert "Acme Corp" in data["subject"]
        assert "<html>" in data["html_body"]
        assert "Acme Corp" in data["html_body"]
        assert data["sample_subscriber_email"] == "subscriber@example.com"
        assert data["sample_decline_code"] == "card_expired"

    def test_friendly_tone_uses_friendly_copy(self, auth_client, account):
        account.company_name = "Acme"
        account.save()
        response = auth_client.get(f"{self.URL}?tone=friendly")
        assert response.status_code == 200
        data = response.json()["data"]
        # Friendly tone uses "Hey" or "card needs a refresh" in card_expired subject
        assert "refresh" in data["subject"].lower() or "hey" in data["subject"].lower()

    def test_minimal_tone_uses_minimal_copy(self, auth_client, account):
        account.company_name = "Acme"
        account.save()
        response = auth_client.get(f"{self.URL}?tone=minimal")
        assert response.status_code == 200
        data = response.json()["data"]
        assert "Card expired" in data["subject"]

    def test_invalid_tone_rejected(self, auth_client, account):
        response = auth_client.get(f"{self.URL}?tone=shouting")
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "INVALID_TONE"

    def test_works_without_customer_update_url(self, auth_client, account):
        # account fixture has no customer_update_url — preview must still render.
        response = auth_client.get(f"{self.URL}?tone=professional")
        assert response.status_code == 200
        # placeholder URL should appear in the rendered HTML
        assert "https://" in response.json()["data"]["html_body"]

    def test_works_for_free_tier(self, auth_client, account):
        account.tier = "free"
        account.save()
        response = auth_client.get(f"{self.URL}?tone=professional")
        assert response.status_code == 200

    def test_works_without_dpa(self, auth_client, account):
        # account fixture has no DPA accepted — preview is a sales surface.
        assert account.dpa_accepted is False
        response = auth_client.get(f"{self.URL}?tone=professional")
        assert response.status_code == 200

    def test_defaults_to_account_saved_tone_when_no_query_param(self, auth_client, account):
        account.notification_tone = "minimal"
        account.save()
        response = auth_client.get(self.URL)
        assert response.status_code == 200
        assert response.json()["data"]["tone"] == "minimal"

    def test_requires_authentication(self, db):
        client = APIClient()
        response = client.get(f"{self.URL}?tone=professional")
        assert response.status_code == 401
