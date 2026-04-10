"""
Tests for Stripe Connect OAuth views.
Uses pytest + DRF APIClient + unittest.mock.
"""
import pytest
from unittest.mock import patch

from cryptography.fernet import Fernet

from core.models.account import Account, StripeConnection


@pytest.fixture(autouse=True)
def _fernet_key():
    """Ensure encryption service has a valid Fernet key for all tests."""
    key = Fernet.generate_key().decode()
    with patch.dict("os.environ", {"STRIPE_TOKEN_KEY": key}):
        from core.services import encryption
        encryption._cipher = None  # reset cached cipher
        yield
        encryption._cipher = None  # cleanup


def _get_valid_state(api_client):
    """Get a valid state token from the initiate endpoint."""
    with patch("core.views.stripe.env") as mock_env:
        mock_env.side_effect = lambda key: {
            "STRIPE_REDIRECT_URI": "http://localhost:3000/register/callback",
            "STRIPE_CLIENT_ID": "ca_test123",
            "STRIPE_SECRET_KEY": "sk_test_xxx",
        }.get(key, "")
        with patch("core.services.stripe_client.env") as mock_sc_env:
            mock_sc_env.side_effect = mock_env.side_effect
            response = api_client.post("/api/v1/stripe/connect/")
    return response.json()["data"]["state"]


@pytest.mark.django_db
class TestInitiateStripeConnect:
    def test_returns_oauth_url(self, api_client):
        """POST /api/v1/stripe/connect/ returns a Stripe OAuth URL and state."""
        with patch("core.views.stripe.env") as mock_env:
            mock_env.side_effect = lambda key: {
                "STRIPE_REDIRECT_URI": "http://localhost:3000/register/callback",
            }.get(key, "")
            with patch("core.services.stripe_client.env") as mock_sc_env:
                mock_sc_env.side_effect = lambda key: {
                    "STRIPE_CLIENT_ID": "ca_test123",
                    "STRIPE_SECRET_KEY": "sk_test_xxx",
                }.get(key, "")
                response = api_client.post("/api/v1/stripe/connect/")

        assert response.status_code == 200
        data = response.json()["data"]
        assert "oauth_url" in data
        assert "state" in data
        assert "connect.stripe.com" in data["oauth_url"]
        assert data["state"] in data["oauth_url"]

    def test_no_auth_required(self, api_client):
        """Initiation endpoint is public — unauthenticated request allowed."""
        with patch("core.views.stripe.env") as mock_env:
            mock_env.side_effect = lambda key: "test_value"
            with patch("core.services.stripe_client.env") as mock_sc_env:
                mock_sc_env.side_effect = lambda key: "test_value"
                response = api_client.post("/api/v1/stripe/connect/")
        assert response.status_code != 401


@pytest.mark.django_db
class TestStripeConnectCallback:
    @pytest.fixture(autouse=True)
    def _mock_scan_task(self):
        """Prevent scan_retroactive_failures.delay() from hitting Redis."""
        with patch("core.views.stripe.scan_retroactive_failures") as mock_scan:
            self._mock_scan = mock_scan
            yield

    def _mock_stripe_exchange(self, access_token="sk_test_xxx", stripe_user_id="acct_test"):
        """Return patches for Stripe token exchange and email lookup."""
        mock_result = {"access_token": access_token, "stripe_user_id": stripe_user_id, "livemode": False}
        return (
            patch("core.views.stripe.exchange_oauth_code", return_value=mock_result),
            patch("core.views.stripe.get_stripe_account_email", return_value="founder@example.com"),
        )

    def test_creates_user_account_and_stripe_connection(self, api_client):
        """Successful callback creates User, Account, StripeConnection atomically."""
        state = _get_valid_state(api_client)

        exchange_patch, email_patch = self._mock_stripe_exchange()
        with exchange_patch, email_patch:
            response = api_client.post("/api/v1/stripe/callback/", {"code": "ac_xxx", "state": state})

        assert response.status_code == 200
        data = response.json()["data"]
        assert "access" in data
        assert "refresh" in data
        assert "account_id" in data

        # DB: account exists with mid tier and trial
        account = Account.objects.get(id=data["account_id"])
        assert account.tier == "mid"
        assert account.trial_ends_at is not None
        assert StripeConnection.objects.filter(account=account).exists()

    def test_account_not_staff(self, api_client):
        """Client accounts must never have is_staff=True (NFR-S4)."""
        state = _get_valid_state(api_client)

        exchange_patch, email_patch = self._mock_stripe_exchange()
        with exchange_patch, email_patch:
            response = api_client.post("/api/v1/stripe/callback/", {"code": "ac_xxx", "state": state})

        assert response.status_code == 200
        account = Account.objects.get(id=response.json()["data"]["account_id"])
        assert account.owner.is_staff is False

    def test_invalid_state_rejected(self, api_client):
        """Callback with invalid/expired state returns 400."""
        response = api_client.post("/api/v1/stripe/callback/", {"code": "ac_xxx", "state": "invalid_state"})
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "INVALID_STATE"

    def test_missing_code_returns_400(self, api_client):
        """Callback with missing code returns 400."""
        response = api_client.post("/api/v1/stripe/callback/", {"state": "something"})
        assert response.status_code == 400

    def test_missing_state_returns_400(self, api_client):
        """Callback with missing state returns 400."""
        response = api_client.post("/api/v1/stripe/callback/", {"code": "ac_xxx"})
        assert response.status_code == 400

    def test_stripe_exchange_failure_returns_400(self, api_client):
        """If Stripe token exchange fails, return 400 — no partial records."""
        import stripe
        state = _get_valid_state(api_client)

        with patch("core.views.stripe.exchange_oauth_code", side_effect=stripe.error.AuthenticationError("Stripe failed")):
            response = api_client.post("/api/v1/stripe/callback/", {"code": "bad_code", "state": state})

        assert response.status_code == 400
        assert Account.objects.count() == 0  # No partial records

    def test_idempotent_reconnection(self, api_client):
        """Reconnecting with same stripe_user_id re-issues JWT (no duplicate account)."""
        state1 = _get_valid_state(api_client)
        exchange_patch1, email_patch1 = self._mock_stripe_exchange()
        with exchange_patch1, email_patch1:
            response1 = api_client.post("/api/v1/stripe/callback/", {"code": "ac_xxx", "state": state1})
        assert response1.status_code == 200
        account_id_1 = response1.json()["data"]["account_id"]

        # Second connection with same stripe_user_id
        state2 = _get_valid_state(api_client)
        exchange_patch2, email_patch2 = self._mock_stripe_exchange()
        with exchange_patch2, email_patch2:
            response2 = api_client.post("/api/v1/stripe/callback/", {"code": "ac_xxx_2", "state": state2})
        assert response2.status_code == 200
        account_id_2 = response2.json()["data"]["account_id"]

        assert account_id_1 == account_id_2  # Same account — no duplicate
        assert Account.objects.count() == 1

    def test_trial_ends_at_30_days(self, api_client):
        """New account trial_ends_at is ~30 days from creation (AC3)."""
        from datetime import timedelta
        from django.utils import timezone

        state = _get_valid_state(api_client)
        exchange_patch, email_patch = self._mock_stripe_exchange()
        now = timezone.now()
        with exchange_patch, email_patch:
            response = api_client.post("/api/v1/stripe/callback/", {"code": "ac_xxx", "state": state})

        assert response.status_code == 200
        account = Account.objects.get(id=response.json()["data"]["account_id"])
        # trial_ends_at should be roughly 30 days from now (allow 1 minute tolerance)
        expected = now + timedelta(days=30)
        assert abs((account.trial_ends_at - expected).total_seconds()) < 60

    def test_new_account_triggers_retroactive_scan(self, api_client):
        """New account OAuth triggers scan_retroactive_failures.delay() (AC1 Story 2.2)."""
        state = _get_valid_state(api_client)
        exchange_patch, email_patch = self._mock_stripe_exchange()

        with exchange_patch, email_patch:
            response = api_client.post("/api/v1/stripe/callback/", {"code": "ac_xxx", "state": state})

        assert response.status_code == 200
        account_id = response.json()["data"]["account_id"]
        self._mock_scan.delay.assert_called_once_with(account_id)

    def test_reconnection_does_not_trigger_scan(self, api_client):
        """Reconnecting existing account does NOT trigger retroactive scan."""
        # First connection
        state1 = _get_valid_state(api_client)
        exchange_patch1, email_patch1 = self._mock_stripe_exchange()
        with exchange_patch1, email_patch1:
            api_client.post("/api/v1/stripe/callback/", {"code": "ac_xxx", "state": state1})

        # Reset mock call count for second connection check
        self._mock_scan.reset_mock()

        # Second connection (reconnection)
        state2 = _get_valid_state(api_client)
        exchange_patch2, email_patch2 = self._mock_stripe_exchange()
        with exchange_patch2, email_patch2:
            response = api_client.post("/api/v1/stripe/callback/", {"code": "ac_xxx_2", "state": state2})

        assert response.status_code == 200
        self._mock_scan.delay.assert_not_called()
