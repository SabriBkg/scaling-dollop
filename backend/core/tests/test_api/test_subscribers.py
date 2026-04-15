import pytest
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.engine.labels import DECLINE_CODE_LABELS
from core.engine.state_machine import STATUS_ACTIVE, STATUS_FRAUD_FLAGGED, STATUS_RECOVERED, STATUS_PASSIVE_CHURN
from core.models.account import Account
from core.models.pending_action import PendingAction, STATUS_PENDING
from core.models.subscriber import Subscriber, SubscriberFailure


@pytest.fixture
def second_user(db):
    from django.contrib.auth.models import User

    return User.objects.create_user(
        username="otheruser", email="other@example.com", password="testpass123"
    )


@pytest.fixture
def second_account(second_user):
    return second_user.account


@pytest.fixture
def second_auth_client(second_user):
    api_client = APIClient()
    refresh = RefreshToken.for_user(second_user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")
    return api_client


def _create_subscriber(account, decline_code, amount_cents, status=STATUS_ACTIVE, pi_suffix="", email=None):
    sub = Subscriber.objects.create(
        stripe_customer_id=f"cus_{decline_code}_{amount_cents}{pi_suffix}",
        email=email or f"{decline_code}{pi_suffix}@test.com",
        status=status,
        account=account,
    )
    failure = SubscriberFailure.objects.create(
        subscriber=sub,
        payment_intent_id=f"pi_{decline_code}_{amount_cents}{pi_suffix}",
        decline_code=decline_code,
        amount_cents=amount_cents,
        classified_action="retry_notify",
        failure_created_at=timezone.now(),
        account=account,
    )
    return sub, failure


@pytest.mark.django_db
class TestSubscriberListEndpoint:
    URL = "/api/v1/subscribers/"

    def test_requires_authentication(self, client):
        response = client.get(self.URL)
        assert response.status_code == 401

    def test_returns_data_envelope(self, auth_client, account):
        response = auth_client.get(self.URL)
        assert response.status_code == 200
        body = response.json()
        assert "data" in body
        assert isinstance(body["data"], list)

    def test_empty_account_returns_empty_list(self, auth_client):
        response = auth_client.get(self.URL)
        data = response.json()["data"]
        assert data == []

    def test_returns_subscriber_card_fields(self, auth_client, account):
        _create_subscriber(account, "insufficient_funds", 5000)

        response = auth_client.get(self.URL)
        data = response.json()["data"]
        assert len(data) == 1

        card = data[0]
        assert "id" in card
        assert "stripe_customer_id" in card
        assert "email" in card
        assert "status" in card
        assert "decline_code" in card
        assert "decline_reason" in card
        assert "amount_cents" in card
        assert "needs_attention" in card
        assert "excluded_from_automation" in card

    def test_decline_reason_has_human_label(self, auth_client, account):
        _create_subscriber(account, "insufficient_funds", 5000)

        response = auth_client.get(self.URL)
        card = response.json()["data"][0]
        assert card["decline_reason"] == "Insufficient funds"
        assert card["decline_code"] == "insufficient_funds"

    def test_fraud_flagged_needs_attention(self, auth_client, account):
        sub, _ = _create_subscriber(account, "fraudulent", 2000)
        sub.status = STATUS_FRAUD_FLAGGED
        sub.save(update_fields=["status"])

        response = auth_client.get(self.URL)
        card = response.json()["data"][0]
        assert card["status"] == "fraud_flagged"
        assert card["needs_attention"] is True

    def test_pending_action_needs_attention(self, auth_client, account):
        sub, failure = _create_subscriber(account, "insufficient_funds", 5000)
        PendingAction.objects.create(
            subscriber=sub,
            failure=failure,
            recommended_action="retry_notify",
            recommended_retry_cap=3,
            recommended_payday_aware=True,
            status=STATUS_PENDING,
            account=account,
        )

        response = auth_client.get(self.URL)
        card = response.json()["data"][0]
        assert card["needs_attention"] is True

    def test_attention_first_sorting(self, auth_client, account):
        # Create normal subscriber first
        _create_subscriber(account, "insufficient_funds", 5000, pi_suffix="_normal")
        # Create fraud-flagged subscriber second
        sub_fraud, _ = _create_subscriber(account, "fraudulent", 2000, pi_suffix="_fraud")
        sub_fraud.status = STATUS_FRAUD_FLAGGED
        sub_fraud.save(update_fields=["status"])

        response = auth_client.get(self.URL)
        data = response.json()["data"]
        assert len(data) == 2
        # Fraud-flagged should appear first
        assert data[0]["status"] == "fraud_flagged"
        assert data[0]["needs_attention"] is True

    def test_tenant_isolation(self, auth_client, account, second_auth_client, second_account):
        _create_subscriber(account, "insufficient_funds", 5000, pi_suffix="_a")
        _create_subscriber(second_account, "generic_decline", 9000, pi_suffix="_b")

        response1 = auth_client.get(self.URL)
        data1 = response1.json()["data"]
        assert len(data1) == 1
        assert data1[0]["amount_cents"] == 5000

        response2 = second_auth_client.get(self.URL)
        data2 = response2.json()["data"]
        assert len(data2) == 1
        assert data2[0]["amount_cents"] == 9000

    def test_all_four_statuses(self, auth_client, account):
        sub_active, _ = _create_subscriber(account, "insufficient_funds", 1000, pi_suffix="_active")

        sub_recovered, _ = _create_subscriber(account, "insufficient_funds", 2000, pi_suffix="_recovered")
        sub_recovered.status = STATUS_RECOVERED
        sub_recovered.save(update_fields=["status"])

        sub_churn, _ = _create_subscriber(account, "generic_decline", 3000, pi_suffix="_churn")
        sub_churn.status = STATUS_PASSIVE_CHURN
        sub_churn.save(update_fields=["status"])

        sub_fraud, _ = _create_subscriber(account, "fraudulent", 4000, pi_suffix="_fraud")
        sub_fraud.status = STATUS_FRAUD_FLAGGED
        sub_fraud.save(update_fields=["status"])

        response = auth_client.get(self.URL)
        data = response.json()["data"]
        assert len(data) == 4

        statuses = {card["status"] for card in data}
        assert statuses == {"active", "recovered", "passive_churn", "fraud_flagged"}

    def test_excluded_from_automation_flag(self, auth_client, account):
        sub, _ = _create_subscriber(account, "insufficient_funds", 5000)
        sub.excluded_from_automation = True
        sub.save(update_fields=["excluded_from_automation"])

        response = auth_client.get(self.URL)
        card = response.json()["data"][0]
        assert card["excluded_from_automation"] is True
