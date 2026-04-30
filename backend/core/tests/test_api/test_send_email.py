"""Story 3.3 v1 — tests for POST /api/v1/subscribers/{id}/send-email/."""
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.engine.state_machine import STATUS_ACTIVE
from core.models.audit import AuditLog
from core.models.notification import NotificationOptOut
from core.models.subscriber import Subscriber, SubscriberFailure
from core.services.dpa import CURRENT_DPA_VERSION


URL_TEMPLATE = "/api/v1/subscribers/{id}/send-email/"


@pytest.fixture(autouse=True)
def _clear_throttle_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def mid_account_with_dpa(account):
    account.tier = "mid"
    account.dpa_accepted_at = timezone.now()
    account.dpa_version = CURRENT_DPA_VERSION
    account.save(update_fields=["tier", "dpa_accepted_at", "dpa_version"])
    return account


@pytest.fixture
def subscriber_with_failure(mid_account_with_dpa):
    sub = Subscriber.objects.create(
        stripe_customer_id="cus_test_3_3_v1",
        email="alice@example.com",
        status=STATUS_ACTIVE,
        account=mid_account_with_dpa,
    )
    failure = SubscriberFailure.objects.create(
        subscriber=sub,
        payment_intent_id="pi_test_3_3_v1",
        decline_code="insufficient_funds",
        amount_cents=4500,
        classified_action="retry_notify",
        failure_created_at=timezone.now(),
        account=mid_account_with_dpa,
    )
    return sub, failure


@pytest.fixture
def second_user(db):
    return User.objects.create_user(
        username="otheruser",
        email="other@example.com",
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


@pytest.mark.django_db
class TestSendEmailEndpoint:
    def test_requires_authentication(self, client):
        response = client.post(URL_TEMPLATE.format(id=1))
        assert response.status_code == 401

    def test_dpa_required_returns_403(self, auth_client, account):
        account.tier = "mid"
        account.save(update_fields=["tier"])
        response = auth_client.post(
            URL_TEMPLATE.format(id=1),
            {"email_type": "update_payment", "failure_id": 1},
            format="json",
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "DPA_REQUIRED"

    def test_free_tier_returns_403(self, auth_client, account):
        account.tier = "free"
        account.dpa_accepted_at = timezone.now()
        account.dpa_version = CURRENT_DPA_VERSION
        account.save(update_fields=["tier", "dpa_accepted_at", "dpa_version"])
        response = auth_client.post(
            URL_TEMPLATE.format(id=1),
            {"email_type": "update_payment", "failure_id": 1},
            format="json",
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "TIER_REQUIRED"

    def test_dpa_gate_runs_before_tier_gate(self, auth_client, account):
        # Unsigned + Free → DPA_REQUIRED first (DPA gate is first per AC contract)
        account.tier = "free"
        account.save(update_fields=["tier"])
        response = auth_client.post(
            URL_TEMPLATE.format(id=1),
            {"email_type": "update_payment", "failure_id": 1},
            format="json",
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "DPA_REQUIRED"

    def test_invalid_email_type_returns_400(self, auth_client, mid_account_with_dpa):
        response = auth_client.post(
            URL_TEMPLATE.format(id=1),
            {"email_type": "banana", "failure_id": 1},
            format="json",
        )
        assert response.status_code == 400
        body = response.json()
        assert body["error"]["code"] == "VALIDATION_ERROR"
        assert body["error"]["field"] == "email_type"

    def test_missing_failure_id_returns_400(self, auth_client, mid_account_with_dpa):
        response = auth_client.post(
            URL_TEMPLATE.format(id=1),
            {"email_type": "update_payment"},
            format="json",
        )
        assert response.status_code == 400
        body = response.json()
        assert body["error"]["code"] == "VALIDATION_ERROR"
        assert body["error"]["field"] == "failure_id"

    def test_subscriber_not_found_returns_404(self, auth_client, mid_account_with_dpa):
        response = auth_client.post(
            URL_TEMPLATE.format(id=99999),
            {"email_type": "update_payment", "failure_id": 1},
            format="json",
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND"

    def test_failure_not_found_returns_404(self, auth_client, subscriber_with_failure):
        sub, _ = subscriber_with_failure
        response = auth_client.post(
            URL_TEMPLATE.format(id=sub.id),
            {"email_type": "update_payment", "failure_id": 99999},
            format="json",
        )
        assert response.status_code == 404
        body = response.json()
        assert body["error"]["code"] == "NOT_FOUND"
        assert body["error"]["field"] == "failure_id"

    def test_opt_out_returns_422_no_task_enqueued(
        self, auth_client, mid_account_with_dpa, subscriber_with_failure
    ):
        sub, failure = subscriber_with_failure
        NotificationOptOut.objects.create(
            account=mid_account_with_dpa,
            subscriber_email=sub.email,
        )
        with patch("core.views.send_email.send_dunning_email.delay") as mock_delay:
            response = auth_client.post(
                URL_TEMPLATE.format(id=sub.id),
                {"email_type": "update_payment", "failure_id": failure.id},
                format="json",
            )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "OPT_OUT"
        mock_delay.assert_not_called()
        audit = AuditLog.objects.filter(
            action="email_sent_blocked", subscriber_id=str(sub.id)
        ).first()
        assert audit is not None
        assert audit.metadata["reason"] == "opt_out"
        assert audit.metadata["email_type"] == "update_payment"
        assert audit.metadata["failure_id"] == failure.id

    def test_excluded_returns_422_no_task_enqueued(
        self, auth_client, subscriber_with_failure
    ):
        sub, failure = subscriber_with_failure
        sub.excluded_from_automation = True
        sub.save(update_fields=["excluded_from_automation"])
        with patch("core.views.send_email.send_dunning_email.delay") as mock_delay:
            response = auth_client.post(
                URL_TEMPLATE.format(id=sub.id),
                {"email_type": "update_payment", "failure_id": failure.id},
                format="json",
            )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "EXCLUDED"
        mock_delay.assert_not_called()
        audit = AuditLog.objects.filter(
            action="email_sent_blocked", subscriber_id=str(sub.id)
        ).first()
        assert audit is not None
        assert audit.metadata["reason"] == "excluded"

    def test_happy_path_queues_task_and_writes_audit(
        self, auth_client, subscriber_with_failure
    ):
        sub, failure = subscriber_with_failure
        with patch("core.views.send_email.send_dunning_email.delay") as mock_delay:
            response = auth_client.post(
                URL_TEMPLATE.format(id=sub.id),
                {"email_type": "update_payment", "failure_id": failure.id},
                format="json",
            )
        assert response.status_code == 202
        body = response.json()
        assert body["data"] == {
            "queued": True,
            "email_type": "update_payment",
            "failure_id": failure.id,
        }
        mock_delay.assert_called_once_with(failure.id, "update_payment")
        audit = AuditLog.objects.filter(
            action="email_sent", subscriber_id=str(sub.id)
        ).first()
        assert audit is not None
        assert audit.actor == "client"
        assert audit.metadata["email_type"] == "update_payment"
        assert audit.metadata["trigger"] == "client_manual"
        assert audit.metadata["failure_id"] == failure.id

    @pytest.mark.parametrize(
        "email_type", ["update_payment", "retry_reminder", "final_notice"]
    )
    def test_happy_path_for_each_email_type(
        self, auth_client, subscriber_with_failure, email_type
    ):
        sub, failure = subscriber_with_failure
        with patch("core.views.send_email.send_dunning_email.delay") as mock_delay:
            response = auth_client.post(
                URL_TEMPLATE.format(id=sub.id),
                {"email_type": email_type, "failure_id": failure.id},
                format="json",
            )
        assert response.status_code == 202
        mock_delay.assert_called_once_with(failure.id, email_type)

    def test_tenant_isolation(
        self, auth_client, second_account, mid_account_with_dpa
    ):
        # Set up a subscriber+failure on second_account; first user POSTs to it.
        other_sub = Subscriber.objects.create(
            stripe_customer_id="cus_other",
            email="other_sub@example.com",
            status=STATUS_ACTIVE,
            account=second_account,
        )
        other_failure = SubscriberFailure.objects.create(
            subscriber=other_sub,
            payment_intent_id="pi_other",
            decline_code="insufficient_funds",
            amount_cents=2000,
            classified_action="retry_notify",
            failure_created_at=timezone.now(),
            account=second_account,
        )
        with patch("core.views.send_email.send_dunning_email.delay") as mock_delay:
            response = auth_client.post(
                URL_TEMPLATE.format(id=other_sub.id),
                {"email_type": "update_payment", "failure_id": other_failure.id},
                format="json",
            )
        assert response.status_code == 404
        mock_delay.assert_not_called()

    def test_rate_limit_429_after_10_requests(
        self, auth_client, subscriber_with_failure
    ):
        sub, failure = subscriber_with_failure
        body = {"email_type": "update_payment", "failure_id": failure.id}
        with patch("core.views.send_email.send_dunning_email.delay"):
            for i in range(10):
                response = auth_client.post(
                    URL_TEMPLATE.format(id=sub.id), body, format="json"
                )
                assert response.status_code == 202, f"Request #{i+1} got {response.status_code}"

            response = auth_client.post(
                URL_TEMPLATE.format(id=sub.id), body, format="json"
            )
        assert response.status_code == 429
        assert response.json()["error"]["code"] == "RATE_LIMITED"
        retry_after = response.headers.get("Retry-After")
        assert retry_after is not None
        assert int(retry_after) > 0

    def test_engine_active_gate_bypassed(
        self, auth_client, mid_account_with_dpa, subscriber_with_failure
    ):
        # engine_mode is None by default in v1 → is_engine_active(account) is False.
        assert mid_account_with_dpa.engine_mode is None
        sub, failure = subscriber_with_failure
        with patch("core.views.send_email.send_dunning_email.delay") as mock_delay:
            response = auth_client.post(
                URL_TEMPLATE.format(id=sub.id),
                {"email_type": "update_payment", "failure_id": failure.id},
                format="json",
            )
        assert response.status_code == 202
        mock_delay.assert_called_once()
