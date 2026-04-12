import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.models.account import Account
from core.models.audit import AuditLog


@pytest.fixture
def new_user(db):
    """User with no profile info (simulates post-OAuth state)."""
    user = User.objects.create_user(
        username="newuser@example.com",
        email="newuser@example.com",
    )
    return user


@pytest.fixture
def new_user_client(new_user):
    """Authenticated client for the new user."""
    client = APIClient()
    refresh = RefreshToken.for_user(new_user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")
    return client


@pytest.fixture
def profile_data():
    return {
        "first_name": "Marc",
        "last_name": "Dupont",
        "company_name": "ProductivityPro",
        "password": "SecurePass!2026",
        "password_confirm": "SecurePass!2026",
    }


@pytest.mark.django_db
class TestCompleteProfile:
    URL = "/api/v1/account/complete-profile/"

    def test_valid_submission_updates_user_and_account(self, new_user_client, new_user, profile_data):
        response = new_user_client.post(self.URL, profile_data, format="json")
        assert response.status_code == 200

        data = response.json()["data"]
        assert data["owner"]["first_name"] == "Marc"
        assert data["owner"]["last_name"] == "Dupont"
        assert data["company_name"] == "ProductivityPro"
        assert data["profile_complete"] is True

        new_user.refresh_from_db()
        assert new_user.first_name == "Marc"
        assert new_user.last_name == "Dupont"
        assert new_user.check_password("SecurePass!2026")

    def test_rejects_repeat_submission(self, new_user_client, new_user, profile_data):
        # First submission succeeds
        self.test_valid_submission_updates_user_and_account(new_user_client, new_user, profile_data)

        # Second submission rejected
        response = new_user_client.post(self.URL, profile_data, format="json")
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "PROFILE_ALREADY_COMPLETED"

    def test_rejects_weak_password(self, new_user_client, profile_data):
        profile_data["password"] = "password"
        profile_data["password_confirm"] = "password"
        response = new_user_client.post(self.URL, profile_data, format="json")
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"

    def test_rejects_mismatched_passwords(self, new_user_client, profile_data):
        profile_data["password_confirm"] = "DifferentPass!2026"
        response = new_user_client.post(self.URL, profile_data, format="json")
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"
        assert "match" in response.json()["error"]["message"].lower()

    def test_requires_authentication(self, db):
        client = APIClient()
        response = client.post(self.URL, {}, format="json")
        assert response.status_code == 401

    def test_audit_log_created(self, new_user_client, new_user, profile_data):
        self.test_valid_submission_updates_user_and_account(new_user_client, new_user, profile_data)
        log = AuditLog.objects.filter(action="profile_completed").first()
        assert log is not None
        assert log.actor == "client"
        assert log.outcome == "success"
        assert log.account == new_user.account

    def test_argon2_password_hashing(self, new_user_client, new_user, profile_data):
        self.test_valid_submission_updates_user_and_account(new_user_client, new_user, profile_data)
        new_user.refresh_from_db()
        assert new_user.password.startswith("argon2")


@pytest.mark.django_db
class TestAccountDetail:
    URL = "/api/v1/account/me/"

    def test_returns_profile_fields(self, auth_client, user, account):
        user.first_name = "Test"
        user.last_name = "User"
        user.save()
        account.company_name = "TestCo"
        account.save()

        response = auth_client.get(self.URL)
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["owner"]["first_name"] == "Test"
        assert data["owner"]["last_name"] == "User"
        assert data["owner"]["email"] == user.email
        assert data["company_name"] == "TestCo"
        assert data["profile_complete"] is True
        # Backward compat
        assert data["owner_email"] == user.email

    def test_profile_incomplete_when_no_company(self, auth_client, user, account):
        response = auth_client.get(self.URL)
        data = response.json()["data"]
        assert data["profile_complete"] is False

    def test_tier_computed_fields_present(self, auth_client, account):
        response = auth_client.get(self.URL)
        data = response.json()["data"]
        assert "trial_days_remaining" in data
        assert "next_scan_at" in data
        assert "engine_active" in data

    def test_trial_days_remaining_on_trial(self, auth_client, account):
        from django.utils import timezone
        from datetime import timedelta
        account.tier = "mid"
        account.trial_ends_at = timezone.now() + timedelta(days=15)
        account.save()

        response = auth_client.get(self.URL)
        data = response.json()["data"]
        assert data["trial_days_remaining"] == 14 or data["trial_days_remaining"] == 15

    def test_engine_active_for_mid(self, auth_client, account):
        account.tier = "mid"
        account.save()
        response = auth_client.get(self.URL)
        assert response.json()["data"]["engine_active"] is True

    def test_engine_inactive_for_free(self, auth_client, account):
        account.tier = "free"
        account.save()
        response = auth_client.get(self.URL)
        assert response.json()["data"]["engine_active"] is False


@pytest.mark.django_db
class TestLoginThrottle:
    URL = "/api/v1/auth/token/"

    def test_rate_limiting(self, db):
        from django.core.cache import cache
        cache.clear()

        client = APIClient()
        for i in range(6):
            response = client.post(
                self.URL,
                {"username": "nobody@example.com", "password": "wrong"},
                format="json",
            )
        # 6th request should be throttled
        assert response.status_code == 429

        # Clean up throttle state to not affect other tests
        cache.clear()
