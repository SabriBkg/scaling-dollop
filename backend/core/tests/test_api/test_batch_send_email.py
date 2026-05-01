"""Story 3.4 v1 — tests for POST /api/v1/subscribers/batch-send-email/."""
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


URL = "/api/v1/subscribers/batch-send-email/"


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
        stripe_customer_id="cus_test_3_4_v1_a",
        email="alice@example.com",
        status=STATUS_ACTIVE,
        account=mid_account_with_dpa,
    )
    failure = SubscriberFailure.objects.create(
        subscriber=sub,
        payment_intent_id="pi_test_3_4_v1_a",
        decline_code="insufficient_funds",
        amount_cents=4500,
        classified_action="retry_notify",
        failure_created_at=timezone.now(),
        account=mid_account_with_dpa,
    )
    return sub, failure


@pytest.fixture
def three_subscribers_with_failures(mid_account_with_dpa):
    pairs = []
    for i in range(3):
        sub = Subscriber.objects.create(
            stripe_customer_id=f"cus_test_3_4_v1_{i}",
            email=f"sub{i}@example.com",
            status=STATUS_ACTIVE,
            account=mid_account_with_dpa,
        )
        failure = SubscriberFailure.objects.create(
            subscriber=sub,
            payment_intent_id=f"pi_test_3_4_v1_{i}",
            decline_code="insufficient_funds",
            amount_cents=4500,
            classified_action="retry_notify",
            failure_created_at=timezone.now(),
            account=mid_account_with_dpa,
        )
        pairs.append((sub, failure))
    return pairs


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
class TestBatchSendEmailEndpoint:
    def test_requires_authentication(self, client):
        response = client.post(URL)
        assert response.status_code == 401

    def test_dpa_required_returns_403(self, auth_client, account):
        account.tier = "mid"
        account.save(update_fields=["tier"])
        response = auth_client.post(
            URL,
            {"selections": [
                {"subscriber_id": 1, "failure_id": 1, "email_type": "update_payment"},
            ]},
            format="json",
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "DPA_REQUIRED"

    def test_dpa_first_even_with_malformed_body(self, auth_client, account):
        # Unsigned + Mid + bad body → DPA_REQUIRED first (gate ordering)
        account.tier = "mid"
        account.save(update_fields=["tier"])
        response = auth_client.post(
            URL,
            {"selections": "not a list"},
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
            URL,
            {"selections": [
                {"subscriber_id": 1, "failure_id": 1, "email_type": "update_payment"},
            ]},
            format="json",
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "TIER_REQUIRED"

    def test_missing_selections_returns_400(self, auth_client, mid_account_with_dpa):
        response = auth_client.post(URL, {}, format="json")
        assert response.status_code == 400
        body = response.json()
        assert body["error"]["code"] == "VALIDATION_ERROR"
        assert body["error"]["field"] == "selections"

    def test_empty_selections_returns_400(self, auth_client, mid_account_with_dpa):
        response = auth_client.post(URL, {"selections": []}, format="json")
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"

    def test_oversize_batch_returns_400(self, auth_client, mid_account_with_dpa):
        selections = [
            {"subscriber_id": 1, "failure_id": 1, "email_type": "update_payment"}
            for _ in range(101)
        ]
        response = auth_client.post(URL, {"selections": selections}, format="json")
        assert response.status_code == 400
        body = response.json()
        assert body["error"]["code"] == "VALIDATION_ERROR"
        assert "100" in body["error"]["message"]

    def test_malformed_entry_returns_400(self, auth_client, mid_account_with_dpa):
        response = auth_client.post(
            URL,
            {"selections": [
                {"subscriber_id": "abc", "failure_id": 1, "email_type": "update_payment"},
            ]},
            format="json",
        )
        assert response.status_code == 400
        body = response.json()
        assert body["error"]["code"] == "VALIDATION_ERROR"
        assert body["error"]["field"] == "selections[0].subscriber_id"

    def test_boolean_subscriber_id_rejected(self, auth_client, mid_account_with_dpa):
        response = auth_client.post(
            URL,
            {"selections": [
                {"subscriber_id": True, "failure_id": 1, "email_type": "update_payment"},
            ]},
            format="json",
        )
        assert response.status_code == 400
        assert response.json()["error"]["field"] == "selections[0].subscriber_id"

    def test_boolean_failure_id_rejected(self, auth_client, mid_account_with_dpa):
        response = auth_client.post(
            URL,
            {"selections": [
                {"subscriber_id": 1, "failure_id": True, "email_type": "update_payment"},
            ]},
            format="json",
        )
        assert response.status_code == 400
        assert response.json()["error"]["field"] == "selections[0].failure_id"

    def test_invalid_email_type_returns_400(self, auth_client, mid_account_with_dpa):
        response = auth_client.post(
            URL,
            {"selections": [
                {"subscriber_id": 1, "failure_id": 1, "email_type": "banana"},
            ]},
            format="json",
        )
        assert response.status_code == 400
        assert response.json()["error"]["field"] == "selections[0].email_type"

    def test_non_object_entry_returns_400(self, auth_client, mid_account_with_dpa):
        response = auth_client.post(
            URL,
            {"selections": ["not-an-object"]},
            format="json",
        )
        assert response.status_code == 400
        assert response.json()["error"]["field"] == "selections[0]"

    def test_validation_error_writes_no_audit_no_task(
        self, auth_client, mid_account_with_dpa
    ):
        with patch("core.views.batch_send_email.send_dunning_email.delay") as mock_delay:
            response = auth_client.post(URL, {"selections": []}, format="json")
        assert response.status_code == 400
        mock_delay.assert_not_called()
        assert AuditLog.objects.filter(action="batch_email_send").count() == 0
        assert AuditLog.objects.filter(action="email_sent").count() == 0

    def test_happy_path_queues_one_per_selection(
        self, auth_client, mid_account_with_dpa, three_subscribers_with_failures
    ):
        selections = [
            {"subscriber_id": sub.id, "failure_id": failure.id, "email_type": "update_payment"}
            for sub, failure in three_subscribers_with_failures
        ]
        with patch("core.views.batch_send_email.send_dunning_email.delay") as mock_delay:
            response = auth_client.post(URL, {"selections": selections}, format="json")
        assert response.status_code == 200
        body = response.json()
        assert body["data"] == {
            "queued": 3, "failed": 0, "failures": [], "selections_total": 3,
        }
        assert mock_delay.call_count == 3
        # Per-selection email_sent audit rows
        sent_audits = AuditLog.objects.filter(action="email_sent")
        assert sent_audits.count() == 3
        for audit in sent_audits:
            assert audit.metadata["batch"] is True
            assert audit.metadata["trigger"] == "client_manual"
        # Single summary audit
        summary = AuditLog.objects.filter(action="batch_email_send").first()
        assert summary is not None
        assert summary.outcome == "success"
        assert summary.metadata["queued"] == 3
        assert summary.metadata["failed"] == 0
        assert summary.metadata["selections_total"] == 3
        assert summary.metadata["trigger"] == "client_manual"

    def test_partial_failure_returns_per_row_errors(
        self, auth_client, mid_account_with_dpa, subscriber_with_failure
    ):
        sub, failure = subscriber_with_failure
        selections = [
            {"subscriber_id": sub.id, "failure_id": failure.id, "email_type": "update_payment"},
            {"subscriber_id": sub.id, "failure_id": 99999, "email_type": "update_payment"},
        ]
        with patch("core.views.batch_send_email.send_dunning_email.delay") as mock_delay:
            response = auth_client.post(URL, {"selections": selections}, format="json")
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["queued"] == 1
        assert body["data"]["failed"] == 1
        assert body["data"]["failures"] == [{
            "subscriber_id": sub.id,
            "failure_id": 99999,
            "code": "NOT_FOUND",
            "message": "Failure not found for this subscriber.",
        }]
        assert mock_delay.call_count == 1
        # NOT_FOUND lookup failures don't write email_sent_blocked
        assert AuditLog.objects.filter(action="email_sent_blocked").count() == 0
        # One success audit + one summary audit
        assert AuditLog.objects.filter(action="email_sent").count() == 1
        summary = AuditLog.objects.filter(action="batch_email_send").first()
        assert summary.outcome == "partial"
        assert summary.metadata["queued"] == 1
        assert summary.metadata["failed"] == 1

    def test_invalid_state_blocks_with_audit(
        self, auth_client, mid_account_with_dpa, subscriber_with_failure
    ):
        sub, failure = subscriber_with_failure
        sub.status = "recovered"
        sub.save(update_fields=["status"])
        with patch("core.views.batch_send_email.send_dunning_email.delay") as mock_delay:
            response = auth_client.post(
                URL,
                {"selections": [{
                    "subscriber_id": sub.id, "failure_id": failure.id,
                    "email_type": "update_payment",
                }]},
                format="json",
            )
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["failed"] == 1
        assert body["data"]["failures"][0]["code"] == "INVALID_STATE"
        mock_delay.assert_not_called()
        blocked = AuditLog.objects.filter(action="email_sent_blocked").first()
        assert blocked is not None
        assert blocked.metadata["reason"] == "invalid_state"
        assert blocked.metadata["subscriber_status"] == "recovered"
        assert blocked.metadata["batch"] is True

    def test_opt_out_blocks_with_audit(
        self, auth_client, mid_account_with_dpa, subscriber_with_failure
    ):
        sub, failure = subscriber_with_failure
        NotificationOptOut.objects.create(
            account=mid_account_with_dpa,
            subscriber_email=sub.email,
        )
        with patch("core.views.batch_send_email.send_dunning_email.delay") as mock_delay:
            response = auth_client.post(
                URL,
                {"selections": [{
                    "subscriber_id": sub.id, "failure_id": failure.id,
                    "email_type": "update_payment",
                }]},
                format="json",
            )
        assert response.status_code == 200
        assert response.json()["data"]["failures"][0]["code"] == "OPT_OUT"
        mock_delay.assert_not_called()
        blocked = AuditLog.objects.filter(action="email_sent_blocked").first()
        assert blocked is not None
        assert blocked.metadata["reason"] == "opt_out"

    def test_excluded_blocks_with_audit(
        self, auth_client, mid_account_with_dpa, subscriber_with_failure
    ):
        sub, failure = subscriber_with_failure
        sub.excluded_from_automation = True
        sub.save(update_fields=["excluded_from_automation"])
        with patch("core.views.batch_send_email.send_dunning_email.delay") as mock_delay:
            response = auth_client.post(
                URL,
                {"selections": [{
                    "subscriber_id": sub.id, "failure_id": failure.id,
                    "email_type": "update_payment",
                }]},
                format="json",
            )
        assert response.status_code == 200
        assert response.json()["data"]["failures"][0]["code"] == "EXCLUDED"
        mock_delay.assert_not_called()
        blocked = AuditLog.objects.filter(action="email_sent_blocked").first()
        assert blocked is not None
        assert blocked.metadata["reason"] == "excluded"

    def test_summary_outcome_failed_when_no_successes(
        self, auth_client, mid_account_with_dpa, subscriber_with_failure
    ):
        sub, failure = subscriber_with_failure
        NotificationOptOut.objects.create(
            account=mid_account_with_dpa,
            subscriber_email=sub.email,
        )
        with patch("core.views.batch_send_email.send_dunning_email.delay"):
            response = auth_client.post(
                URL,
                {"selections": [{
                    "subscriber_id": sub.id, "failure_id": failure.id,
                    "email_type": "update_payment",
                }]},
                format="json",
            )
        assert response.status_code == 200
        summary = AuditLog.objects.filter(action="batch_email_send").first()
        assert summary.outcome == "failed"
        assert summary.metadata["queued"] == 0
        assert summary.metadata["failed"] == 1

    def test_tenant_isolation(
        self, auth_client, mid_account_with_dpa, second_account
    ):
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
        with patch("core.views.batch_send_email.send_dunning_email.delay") as mock_delay:
            response = auth_client.post(
                URL,
                {"selections": [{
                    "subscriber_id": other_sub.id,
                    "failure_id": other_failure.id,
                    "email_type": "update_payment",
                }]},
                format="json",
            )
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["failed"] == 1
        assert body["data"]["failures"][0]["code"] == "NOT_FOUND"
        mock_delay.assert_not_called()

    def test_rate_limit_429_after_5_requests(
        self, auth_client, mid_account_with_dpa, subscriber_with_failure
    ):
        sub, failure = subscriber_with_failure
        body = {"selections": [{
            "subscriber_id": sub.id, "failure_id": failure.id,
            "email_type": "update_payment",
        }]}
        with patch("core.views.batch_send_email.send_dunning_email.delay"):
            for i in range(5):
                response = auth_client.post(URL, body, format="json")
                assert response.status_code == 200, f"Request #{i+1} got {response.status_code}"
            response = auth_client.post(URL, body, format="json")
        assert response.status_code == 429
        assert response.json()["error"]["code"] == "RATE_LIMITED"
        retry_after = response.headers.get("Retry-After")
        assert retry_after is not None
        assert int(retry_after) > 0

    def test_batch_throttle_independent_of_per_row(
        self, auth_client, mid_account_with_dpa, subscriber_with_failure
    ):
        sub, failure = subscriber_with_failure
        per_row_url = f"/api/v1/subscribers/{sub.id}/send-email/"
        per_row_body = {"email_type": "update_payment", "failure_id": failure.id}
        with patch("core.views.send_email.send_dunning_email.delay"), \
             patch("core.views.batch_send_email.send_dunning_email.delay"):
            for _ in range(10):
                resp = auth_client.post(per_row_url, per_row_body, format="json")
                assert resp.status_code == 202
            # 11th per-row should be throttled
            resp = auth_client.post(per_row_url, per_row_body, format="json")
            assert resp.status_code == 429
            # Batch endpoint independent — should still go through.
            batch_body = {"selections": [{
                "subscriber_id": sub.id, "failure_id": failure.id,
                "email_type": "update_payment",
            }]}
            batch_resp = auth_client.post(URL, batch_body, format="json")
        assert batch_resp.status_code == 200

    def test_request_with_two_email_types_routes_correctly(
        self, auth_client, mid_account_with_dpa, three_subscribers_with_failures
    ):
        sub_a, failure_a = three_subscribers_with_failures[0]
        sub_b, failure_b = three_subscribers_with_failures[1]
        selections = [
            {"subscriber_id": sub_a.id, "failure_id": failure_a.id, "email_type": "update_payment"},
            {"subscriber_id": sub_b.id, "failure_id": failure_b.id, "email_type": "final_notice"},
        ]
        with patch("core.views.batch_send_email.send_dunning_email.delay") as mock_delay:
            response = auth_client.post(URL, {"selections": selections}, format="json")
        assert response.status_code == 200
        assert response.json()["data"]["queued"] == 2
        # Two distinct delay calls with the right email_type.
        called_args = sorted(
            (call.args[0], call.args[1]) for call in mock_delay.call_args_list
        )
        expected = sorted(
            ((failure_a.id, "update_payment"), (failure_b.id, "final_notice"))
        )
        assert called_args == expected

    def test_duplicate_selection_in_batch_double_dispatches(
        self, auth_client, mid_account_with_dpa, subscriber_with_failure
    ):
        sub, failure = subscriber_with_failure
        entry = {
            "subscriber_id": sub.id, "failure_id": failure.id,
            "email_type": "update_payment",
        }
        with patch("core.views.batch_send_email.send_dunning_email.delay") as mock_delay:
            response = auth_client.post(
                URL, {"selections": [entry, entry]}, format="json",
            )
        assert response.status_code == 200
        assert response.json()["data"]["queued"] == 2
        assert mock_delay.call_count == 2

