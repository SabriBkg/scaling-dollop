"""Tests for the Stripe billing webhook and checkout session endpoints."""
import json
import pytest
from datetime import timedelta
from unittest.mock import patch, MagicMock

from django.utils import timezone

from core.models.account import TIER_FREE, TIER_MID
from core.models.audit import AuditLog


@pytest.mark.django_db
class TestStripeBillingWebhook:
    def _post_webhook(self, api_client, payload, sig="valid_sig"):
        return api_client.post(
            "/api/v1/billing/webhook/",
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE=sig,
        )

    @patch("core.views.billing.stripe.Webhook.construct_event")
    def test_checkout_completed_upgrades_account(self, mock_construct, api_client, account):
        """checkout.session.completed upgrades account to Mid."""
        account.tier = TIER_FREE
        account.save()

        event = {
            "type": "checkout.session.completed",
            "data": {"object": {"client_reference_id": str(account.id)}},
        }
        mock_construct.return_value = event

        response = self._post_webhook(api_client, event)
        assert response.status_code == 200

        account.refresh_from_db()
        assert account.tier == TIER_MID
        assert account.trial_ends_at is None

    @patch("core.views.billing.stripe.Webhook.construct_event")
    def test_checkout_completed_writes_audit(self, mock_construct, api_client, account):
        """Upgrade writes an audit event."""
        account.tier = TIER_FREE
        account.save()

        event = {
            "type": "checkout.session.completed",
            "data": {"object": {"client_reference_id": str(account.id)}},
        }
        mock_construct.return_value = event

        self._post_webhook(api_client, event)

        audit = AuditLog.objects.filter(action="subscription_upgraded", account=account).first()
        assert audit is not None
        assert audit.outcome == "success"

    @patch("core.views.billing.stripe.Webhook.construct_event")
    def test_subscription_deleted_downgrades(self, mock_construct, api_client, account):
        """customer.subscription.deleted downgrades to Free."""
        account.tier = TIER_MID
        account.trial_ends_at = None
        account.save()

        event = {
            "type": "customer.subscription.deleted",
            "data": {"object": {"metadata": {"account_id": str(account.id)}}},
        }
        mock_construct.return_value = event

        response = self._post_webhook(api_client, event)
        assert response.status_code == 200

        account.refresh_from_db()
        assert account.tier == TIER_FREE

    @patch("core.views.billing.stripe.Webhook.construct_event")
    def test_unhandled_event_returns_200(self, mock_construct, api_client):
        """Unhandled event types return 200 (Stripe best practice)."""
        event = {
            "type": "invoice.created",
            "data": {"object": {}},
        }
        mock_construct.return_value = event

        response = self._post_webhook(api_client, event)
        assert response.status_code == 200

    @patch("core.views.billing.stripe.Webhook.construct_event")
    def test_invalid_signature_returns_400(self, mock_construct, api_client):
        """Invalid signature returns 400."""
        import stripe
        mock_construct.side_effect = stripe.StripeError("Invalid signature")

        response = self._post_webhook(api_client, {})
        assert response.status_code == 400

    @patch("core.views.billing.stripe.Webhook.construct_event")
    def test_idempotent_upgrade(self, mock_construct, api_client, account):
        """Re-processing checkout.session.completed for already-Mid account is safe."""
        account.tier = TIER_MID
        account.trial_ends_at = None
        account.save()

        event = {
            "type": "checkout.session.completed",
            "data": {"object": {"client_reference_id": str(account.id)}},
        }
        mock_construct.return_value = event

        response = self._post_webhook(api_client, event)
        assert response.status_code == 200

        account.refresh_from_db()
        assert account.tier == TIER_MID


@pytest.mark.django_db
class TestCreateCheckoutSession:
    @patch("core.views.billing.stripe.checkout.Session.create")
    def test_creates_session(self, mock_create, auth_client, account):
        """Authenticated user can create a checkout session."""
        mock_create.return_value = MagicMock(url="https://checkout.stripe.com/session123")

        response = auth_client.post("/api/v1/billing/checkout/")
        assert response.status_code == 200
        assert response.json()["data"]["checkout_url"] == "https://checkout.stripe.com/session123"

    def test_unauthenticated_rejected(self, api_client):
        """Unauthenticated request returns 401."""
        response = api_client.post("/api/v1/billing/checkout/")
        assert response.status_code == 401

    @patch("core.views.billing.stripe.checkout.Session.create")
    def test_stripe_error_returns_500(self, mock_create, auth_client):
        """Stripe error returns 500."""
        import stripe
        mock_create.side_effect = stripe.StripeError("error")

        response = auth_client.post("/api/v1/billing/checkout/")
        assert response.status_code == 500
