from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.engine.state_machine import (
    STATUS_ACTIVE,
    STATUS_FRAUD_FLAGGED,
)
from core.models.notification import NotificationLog
from core.models.subscriber import Subscriber, SubscriberFailure


@pytest.fixture
def second_user(db):
    from django.contrib.auth.models import User

    return User.objects.create_user(
        username="otheruser2",
        email="other2@example.com",
        password="testpass123",
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


def _create_subscriber(
    account,
    decline_code,
    amount_cents,
    *,
    status=STATUS_ACTIVE,
    pi_suffix="",
    email=None,
    failure_created_at=None,
):
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
        failure_created_at=failure_created_at or timezone.now(),
        account=account,
    )
    return sub, failure


@pytest.mark.django_db
class TestFailedPaymentsListEndpoint:
    URL = "/api/v1/dashboard/failed-payments/"

    def test_requires_authentication(self, client):
        response = client.get(self.URL)
        assert response.status_code == 401

    def test_empty_account_returns_empty_data_array(self, auth_client):
        response = auth_client.get(self.URL)
        assert response.status_code == 200
        body = response.json()
        assert body == {"data": []}

    def test_returns_only_current_month_failures(self, auth_client, account):
        now = timezone.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # This-month row (now)
        _create_subscriber(account, "insufficient_funds", 1000, pi_suffix="_this")

        # Last-day-of-previous-month row
        _create_subscriber(
            account,
            "card_expired",
            2000,
            pi_suffix="_prev",
            failure_created_at=month_start - timedelta(seconds=1),
        )

        # Later this-month row
        _create_subscriber(
            account,
            "do_not_honor",
            3000,
            pi_suffix="_later",
            failure_created_at=now + timedelta(days=1),
        )

        data = auth_client.get(self.URL).json()["data"]
        amounts = {row["amount_cents"] for row in data}
        assert amounts == {1000, 3000}

    def test_sort_by_date_desc_default(self, auth_client, account):
        now = timezone.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # Three failures across this month with distinct timestamps.
        _create_subscriber(
            account,
            "insufficient_funds",
            1000,
            pi_suffix="_a",
            failure_created_at=month_start + timedelta(hours=1),
        )
        _create_subscriber(
            account,
            "insufficient_funds",
            2000,
            pi_suffix="_b",
            failure_created_at=month_start + timedelta(days=2),
        )
        _create_subscriber(
            account,
            "insufficient_funds",
            3000,
            pi_suffix="_c",
            failure_created_at=month_start + timedelta(days=5),
        )

        data = auth_client.get(self.URL).json()["data"]
        timestamps = [row["failure_created_at"] for row in data]
        assert timestamps == sorted(timestamps, reverse=True)

    def test_sort_by_amount_asc(self, auth_client, account):
        _create_subscriber(account, "insufficient_funds", 5000, pi_suffix="_a")
        _create_subscriber(account, "insufficient_funds", 1000, pi_suffix="_b")
        _create_subscriber(account, "insufficient_funds", 9000, pi_suffix="_c")

        data = auth_client.get(self.URL + "?sort=amount&dir=asc").json()["data"]
        amounts = [row["amount_cents"] for row in data]
        assert amounts == [1000, 5000, 9000]

    def test_sort_by_amount_desc(self, auth_client, account):
        _create_subscriber(account, "insufficient_funds", 5000, pi_suffix="_a")
        _create_subscriber(account, "insufficient_funds", 1000, pi_suffix="_b")
        _create_subscriber(account, "insufficient_funds", 9000, pi_suffix="_c")

        data = auth_client.get(self.URL + "?sort=amount&dir=desc").json()["data"]
        amounts = [row["amount_cents"] for row in data]
        assert amounts == [9000, 5000, 1000]

    def test_invalid_sort_returns_400(self, auth_client):
        response = auth_client.get(self.URL + "?sort=banana")
        assert response.status_code == 400
        body = response.json()
        assert body["error"]["code"] == "VALIDATION_ERROR"
        assert body["error"]["field"] == "sort"

    def test_invalid_dir_returns_400(self, auth_client):
        response = auth_client.get(self.URL + "?dir=sideways")
        assert response.status_code == 400
        body = response.json()
        assert body["error"]["code"] == "VALIDATION_ERROR"
        assert body["error"]["field"] == "dir"

    def test_decline_reason_translated(self, auth_client, account):
        _create_subscriber(account, "insufficient_funds", 5000)
        data = auth_client.get(self.URL).json()["data"]
        assert data[0]["decline_reason"] == "Insufficient funds"

    def test_unknown_decline_code_falls_back_to_default_label(self, auth_client, account):
        _create_subscriber(account, "totally_unknown", 5000)
        data = auth_client.get(self.URL).json()["data"]
        assert data[0]["decline_reason"] == "Payment declined"

    def test_recommended_email_type_is_null_in_v1(self, auth_client, account):
        _create_subscriber(account, "insufficient_funds", 5000)
        data = auth_client.get(self.URL).json()["data"]
        assert data[0]["recommended_email_type"] is None

    def test_last_email_sent_at_null_when_no_notification(self, auth_client, account):
        _create_subscriber(account, "insufficient_funds", 5000)
        data = auth_client.get(self.URL).json()["data"]
        assert data[0]["last_email_sent_at"] is None

    def test_last_email_sent_at_uses_most_recent_sent_log(self, auth_client, account):
        sub, failure = _create_subscriber(account, "insufficient_funds", 5000)

        sent_log = NotificationLog.objects.create(
            account=account,
            subscriber=sub,
            failure=failure,
            email_type="failure_notice",
            status="sent",
        )

        # A more-recent failed log should not surface as "last email sent".
        NotificationLog.objects.create(
            account=account,
            subscriber=sub,
            failure=failure,
            email_type="final_notice",
            status="failed",
        )

        data = auth_client.get(self.URL).json()["data"]
        assert data[0]["last_email_sent_at"] is not None
        # Match the timestamp of the SENT row, not the failed row.
        # DRF emits ISO 8601 with 'Z'; Python's isoformat uses '+00:00'.
        expected = sent_log.created_at.isoformat().replace("+00:00", "Z")
        assert data[0]["last_email_sent_at"] == expected

    def test_fraud_flagged_subscriber_status_in_response(self, auth_client, account):
        sub, _ = _create_subscriber(account, "fraudulent", 4000)
        sub.status = STATUS_FRAUD_FLAGGED
        sub.save(update_fields=["status"])

        data = auth_client.get(self.URL).json()["data"]
        assert data[0]["subscriber_status"] == "fraud_flagged"

    def test_tenant_isolation(
        self, auth_client, account, second_auth_client, second_account
    ):
        _create_subscriber(account, "insufficient_funds", 5000, pi_suffix="_a")
        _create_subscriber(second_account, "generic_decline", 9000, pi_suffix="_b")

        data1 = auth_client.get(self.URL).json()["data"]
        assert len(data1) == 1
        assert data1[0]["amount_cents"] == 5000

        data2 = second_auth_client.get(self.URL).json()["data"]
        assert len(data2) == 1
        assert data2[0]["amount_cents"] == 9000

    def test_response_row_shape(self, auth_client, account):
        _create_subscriber(account, "insufficient_funds", 5000)
        data = auth_client.get(self.URL).json()["data"]
        row = data[0]
        for key in (
            "id",
            "subscriber_id",
            "subscriber_email",
            "subscriber_stripe_customer_id",
            "subscriber_status",
            "decline_code",
            "decline_reason",
            "amount_cents",
            "failure_created_at",
            "recommended_email_type",
            "last_email_sent_at",
            "payment_method_country",
            "excluded_from_automation",
        ):
            assert key in row, f"missing key: {key}"

    def test_notification_log_tenant_isolation(
        self, auth_client, account, second_account
    ):
        """A NotificationLog scoped to a different account must not surface as last_email_sent_at."""
        sub, failure = _create_subscriber(account, "insufficient_funds", 5000)

        NotificationLog.objects.create(
            account=second_account,
            subscriber=sub,
            failure=failure,
            email_type="failure_notice",
            status="sent",
        )

        data = auth_client.get(self.URL).json()["data"]
        assert data[0]["last_email_sent_at"] is None
