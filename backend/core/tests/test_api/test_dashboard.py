import pytest
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.engine.labels import DECLINE_CODE_LABELS
from core.engine.state_machine import STATUS_ACTIVE, STATUS_RECOVERED, STATUS_FRAUD_FLAGGED
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


def _create_failure(account, decline_code, amount_cents, status=STATUS_ACTIVE, pi_suffix=""):
    sub = Subscriber.objects.create(
        stripe_customer_id=f"cus_{decline_code}_{amount_cents}{pi_suffix}",
        email=f"{decline_code}@test.com",
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
class TestDashboardSummaryEndpoint:
    URL = "/api/v1/dashboard/summary/"

    def test_requires_authentication(self, client):
        response = client.get(self.URL)
        assert response.status_code == 401

    def test_returns_data_envelope(self, auth_client):
        response = auth_client.get(self.URL)
        assert response.status_code == 200
        body = response.json()
        assert "data" in body
        data = body["data"]
        assert "total_failures" in data
        assert "total_subscribers" in data
        assert "estimated_recoverable_cents" in data
        assert "recovered_this_month_cents" in data
        assert "recovered_count" in data
        assert "recovery_rate" in data
        assert "net_benefit_cents" in data
        assert "decline_breakdown" in data

    def test_empty_account_returns_zeros(self, auth_client):
        response = auth_client.get(self.URL)
        data = response.json()["data"]
        assert data["total_failures"] == 0
        assert data["total_subscribers"] == 0
        assert data["estimated_recoverable_cents"] == 0
        assert data["recovered_this_month_cents"] == 0
        assert data["recovered_count"] == 0
        assert data["recovery_rate"] == 0
        assert data["net_benefit_cents"] == 0
        assert data["decline_breakdown"] == []

    def test_aggregation_accuracy(self, auth_client, account):
        cache.clear()
        _create_failure(account, "insufficient_funds", 5000, pi_suffix="_1")
        _create_failure(account, "insufficient_funds", 3000, pi_suffix="_2")
        _create_failure(account, "fraudulent", 2000, pi_suffix="_3")

        response = auth_client.get(self.URL)
        data = response.json()["data"]

        assert data["total_failures"] == 3
        assert data["total_subscribers"] == 3
        # fraudulent is non-recoverable, so only the two insufficient_funds
        assert data["estimated_recoverable_cents"] == 8000

    def test_decline_breakdown_has_human_labels(self, auth_client, account):
        cache.clear()
        _create_failure(account, "insufficient_funds", 5000)
        _create_failure(account, "card_expired", 3000)

        response = auth_client.get(self.URL)
        breakdown = response.json()["data"]["decline_breakdown"]

        labels = {entry["human_label"] for entry in breakdown}
        assert "Insufficient funds" in labels
        assert "Card expired" in labels
        # No raw stripe codes
        codes_in_labels = {entry["human_label"] for entry in breakdown}
        assert "insufficient_funds" not in codes_in_labels
        assert "card_expired" not in codes_in_labels

    def test_decline_breakdown_no_raw_codes_in_labels(self, auth_client, account):
        cache.clear()
        _create_failure(account, "do_not_honor", 1000)

        response = auth_client.get(self.URL)
        breakdown = response.json()["data"]["decline_breakdown"]
        for entry in breakdown:
            assert entry["human_label"] != entry["decline_code"]

    def test_cache_behavior(self, auth_client, account):
        cache.clear()
        _create_failure(account, "insufficient_funds", 5000)

        # First call populates cache
        response1 = auth_client.get(self.URL)
        data1 = response1.json()["data"]
        assert data1["total_failures"] == 1

        # Add another failure — cached response should still show 1
        _create_failure(account, "generic_decline", 2000)
        response2 = auth_client.get(self.URL)
        data2 = response2.json()["data"]
        assert data2["total_failures"] == 1  # Still cached

        # Clear cache — should now show 2
        cache.clear()
        response3 = auth_client.get(self.URL)
        data3 = response3.json()["data"]
        assert data3["total_failures"] == 2

    def test_tenant_isolation(self, auth_client, account, second_auth_client, second_account):
        cache.clear()
        _create_failure(account, "insufficient_funds", 5000)
        _create_failure(second_account, "generic_decline", 9000, pi_suffix="_other")

        # First user sees only their data
        response1 = auth_client.get(self.URL)
        data1 = response1.json()["data"]
        assert data1["total_failures"] == 1
        assert data1["estimated_recoverable_cents"] == 5000

        # Second user sees only their data
        response2 = second_auth_client.get(self.URL)
        data2 = response2.json()["data"]
        assert data2["total_failures"] == 1
        assert data2["estimated_recoverable_cents"] == 9000

    def test_recovered_this_month(self, auth_client, account):
        cache.clear()
        sub, _ = _create_failure(account, "insufficient_funds", 5000)
        sub.status = STATUS_RECOVERED
        sub.save()

        response = auth_client.get(self.URL)
        data = response.json()["data"]
        assert data["recovered_count"] == 1
        assert data["recovered_this_month_cents"] == 5000

    def test_recovery_rate_calculation(self, auth_client, account):
        cache.clear()
        sub1, _ = _create_failure(account, "insufficient_funds", 5000, pi_suffix="_a")
        sub2, _ = _create_failure(account, "generic_decline", 3000, pi_suffix="_b")
        sub1.status = STATUS_RECOVERED
        sub1.save()

        response = auth_client.get(self.URL)
        data = response.json()["data"]
        assert data["recovery_rate"] == 50.0

    def test_monetary_values_are_integers(self, auth_client, account):
        cache.clear()
        _create_failure(account, "insufficient_funds", 5000)

        response = auth_client.get(self.URL)
        data = response.json()["data"]
        assert isinstance(data["estimated_recoverable_cents"], int)
        assert isinstance(data["recovered_this_month_cents"], int)
        assert isinstance(data["net_benefit_cents"], int)


    def test_attention_items_empty_by_default(self, auth_client, account):
        cache.clear()
        response = auth_client.get(self.URL)
        data = response.json()["data"]
        assert "attention_items" in data
        assert data["attention_items"] == []

    def test_attention_items_fraud_flag(self, auth_client, account):
        cache.clear()
        sub, _ = _create_failure(account, "fraudulent", 2000)
        sub.status = STATUS_FRAUD_FLAGGED
        sub.save(update_fields=["status"])

        response = auth_client.get(self.URL)
        items = response.json()["data"]["attention_items"]
        assert len(items) >= 1
        fraud_items = [i for i in items if i["type"] == "fraud_flag"]
        assert len(fraud_items) == 1
        assert fraud_items[0]["subscriber_id"] == sub.id

    def test_attention_items_pending_action(self, auth_client, account):
        cache.clear()
        sub, failure = _create_failure(account, "insufficient_funds", 5000)
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
        items = response.json()["data"]["attention_items"]
        pending_items = [i for i in items if i["type"] == "pending_action"]
        assert len(pending_items) == 1
        assert pending_items[0]["subscriber_id"] == sub.id

    def test_attention_items_retry_cap(self, auth_client, account):
        cache.clear()
        sub, failure = _create_failure(account, "insufficient_funds", 5000)
        # insufficient_funds has retry_cap=3, set retry_count=2 (>= 3-1)
        failure.retry_count = 2
        failure.save(update_fields=["retry_count"])

        response = auth_client.get(self.URL)
        items = response.json()["data"]["attention_items"]
        retry_items = [i for i in items if i["type"] == "retry_cap"]
        assert len(retry_items) == 1
        assert retry_items[0]["subscriber_id"] == sub.id

    def test_attention_item_structure(self, auth_client, account):
        cache.clear()
        sub, _ = _create_failure(account, "fraudulent", 2000)
        sub.status = STATUS_FRAUD_FLAGGED
        sub.save(update_fields=["status"])

        response = auth_client.get(self.URL)
        item = response.json()["data"]["attention_items"][0]
        assert "type" in item
        assert "subscriber_id" in item
        assert "subscriber_name" in item
        assert "label" in item


@pytest.mark.django_db
class TestDeclineCodeLabels:
    def test_all_decline_rules_have_labels(self):
        from core.engine.rules import DECLINE_RULES

        for code in DECLINE_RULES:
            label = DECLINE_CODE_LABELS.get(code, DECLINE_CODE_LABELS.get("_default"))
            assert label is not None, f"No label for decline code: {code}"
            assert label != code or code == "_default", f"Label for {code} is just the raw code"

    def test_default_label_exists(self):
        assert "_default" in DECLINE_CODE_LABELS
        assert DECLINE_CODE_LABELS["_default"] == "Payment declined"
