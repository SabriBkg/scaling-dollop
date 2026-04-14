"""
Tests for batch action API endpoints.
Covers: pending list, batch approval, subscriber exclusion, pending count, tenant isolation.
"""
import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.models.account import Account
from core.models.audit import AuditLog
from core.models.pending_action import PendingAction
from core.models.subscriber import Subscriber, SubscriberFailure


@pytest.mark.django_db
class TestPendingActionList:
    URL = "/api/v1/actions/pending/"

    @pytest.fixture
    def supervised_account(self, account):
        account.tier = "mid"
        account.dpa_accepted_at = timezone.now()
        account.engine_mode = "supervised"
        account.save()
        return account

    @pytest.fixture
    def subscriber(self, supervised_account):
        return Subscriber.objects.create(
            account=supervised_account,
            stripe_customer_id="cus_test",
            email="user@example.com",
        )

    @pytest.fixture
    def pending_action(self, supervised_account, subscriber):
        failure = SubscriberFailure.objects.create(
            account=supervised_account,
            subscriber=subscriber,
            payment_intent_id="pi_test_001",
            decline_code="insufficient_funds",
            amount_cents=5000,
            failure_created_at=timezone.now(),
            classified_action="retry_notify",
        )
        return PendingAction.objects.create(
            account=supervised_account,
            subscriber=subscriber,
            failure=failure,
            recommended_action="retry_notify",
            recommended_retry_cap=3,
            recommended_payday_aware=True,
        )

    def test_list_returns_pending_actions(self, auth_client, supervised_account, pending_action):
        response = auth_client.get(self.URL)
        assert response.status_code == 200

        data = response.json()
        assert data["meta"]["total"] == 1
        item = data["data"][0]
        assert item["id"] == pending_action.id
        assert item["subscriber_name"] == "user@example.com"
        assert item["decline_reason"] == "Insufficient funds"
        assert item["recommended_action"] == "retry_notify"
        assert item["amount_cents"] == 5000

    def test_list_excludes_non_pending(self, auth_client, supervised_account, pending_action):
        pending_action.status = "approved"
        pending_action.save()

        response = auth_client.get(self.URL)
        assert response.json()["meta"]["total"] == 0

    def test_requires_authentication(self, db):
        client = APIClient()
        response = client.get(self.URL)
        assert response.status_code == 401

    def test_tenant_isolation(self, auth_client, supervised_account, pending_action):
        """Can only see own pending actions — not another account's."""
        other_user = User.objects.create_user(
            username="other", email="other@example.com", password="pass123"
        )
        other_account = other_user.account
        other_sub = Subscriber.objects.create(
            account=other_account,
            stripe_customer_id="cus_other",
        )
        other_failure = SubscriberFailure.objects.create(
            account=other_account,
            subscriber=other_sub,
            payment_intent_id="pi_other",
            decline_code="generic_decline",
            amount_cents=1000,
            failure_created_at=timezone.now(),
            classified_action="retry_notify",
        )
        PendingAction.objects.create(
            account=other_account,
            subscriber=other_sub,
            failure=other_failure,
            recommended_action="retry_notify",
            recommended_retry_cap=1,
            recommended_payday_aware=False,
        )

        response = auth_client.get(self.URL)
        # Should only see own pending action
        assert response.json()["meta"]["total"] == 1
        assert response.json()["data"][0]["id"] == pending_action.id


@pytest.mark.django_db
class TestBatchApproval:
    URL = "/api/v1/actions/batch/"

    @pytest.fixture
    def supervised_account(self, account):
        account.tier = "mid"
        account.dpa_accepted_at = timezone.now()
        account.engine_mode = "supervised"
        account.save()
        return account

    @pytest.fixture
    def subscriber(self, supervised_account):
        return Subscriber.objects.create(
            account=supervised_account,
            stripe_customer_id="cus_batch",
            email="batch@example.com",
        )

    @pytest.fixture
    def pending_action(self, supervised_account, subscriber):
        failure = SubscriberFailure.objects.create(
            account=supervised_account,
            subscriber=subscriber,
            payment_intent_id="pi_batch_001",
            decline_code="insufficient_funds",
            amount_cents=3000,
            failure_created_at=timezone.now(),
            classified_action="retry_notify",
        )
        return PendingAction.objects.create(
            account=supervised_account,
            subscriber=subscriber,
            failure=failure,
            recommended_action="retry_notify",
            recommended_retry_cap=3,
            recommended_payday_aware=True,
        )

    def test_batch_approval_executes_actions(self, auth_client, supervised_account, pending_action):
        response = auth_client.post(self.URL, {"action_ids": [pending_action.id]}, format="json")
        assert response.status_code == 200

        data = response.json()["data"]
        assert data["approved"] == 1
        assert data["failed"] == 0

        pending_action.refresh_from_db()
        assert pending_action.status == "approved"

    def test_batch_creates_audit_event(self, auth_client, supervised_account, pending_action):
        auth_client.post(self.URL, {"action_ids": [pending_action.id]}, format="json")

        log = AuditLog.objects.filter(action="batch_actions_approved").first()
        assert log is not None
        assert log.actor == "client"
        assert log.metadata["approved"] == 1

    def test_partial_failure_returns_200(self, auth_client, supervised_account, pending_action):
        """AC3: Partial batch failure returns 200 with both counts."""
        response = auth_client.post(
            self.URL,
            {"action_ids": [pending_action.id, 99999]},
            format="json",
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["approved"] == 1

    def test_empty_action_ids_returns_400(self, auth_client, supervised_account):
        response = auth_client.post(self.URL, {"action_ids": []}, format="json")
        assert response.status_code == 400

    def test_requires_authentication(self, db):
        client = APIClient()
        response = client.post(self.URL, {"action_ids": [1]}, format="json")
        assert response.status_code == 401


@pytest.mark.django_db
class TestSubscriberExclusion:
    @pytest.fixture
    def supervised_account(self, account):
        account.tier = "mid"
        account.dpa_accepted_at = timezone.now()
        account.engine_mode = "supervised"
        account.save()
        return account

    @pytest.fixture
    def subscriber(self, supervised_account):
        return Subscriber.objects.create(
            account=supervised_account,
            stripe_customer_id="cus_excl",
            email="exclude@example.com",
        )

    @pytest.fixture
    def pending_action(self, supervised_account, subscriber):
        failure = SubscriberFailure.objects.create(
            account=supervised_account,
            subscriber=subscriber,
            payment_intent_id="pi_excl_001",
            decline_code="generic_decline",
            amount_cents=2000,
            failure_created_at=timezone.now(),
            classified_action="retry_notify",
        )
        return PendingAction.objects.create(
            account=supervised_account,
            subscriber=subscriber,
            failure=failure,
            recommended_action="retry_notify",
            recommended_retry_cap=1,
            recommended_payday_aware=False,
        )

    def test_exclusion_sets_flag(self, auth_client, supervised_account, subscriber, pending_action):
        url = f"/api/v1/subscribers/{subscriber.id}/exclude/"
        response = auth_client.post(url)
        assert response.status_code == 200

        data = response.json()["data"]
        assert data["excluded"] is True

        subscriber.refresh_from_db()
        assert subscriber.excluded_from_automation is True

    def test_exclusion_marks_pending_actions_excluded(
        self, auth_client, supervised_account, subscriber, pending_action
    ):
        url = f"/api/v1/subscribers/{subscriber.id}/exclude/"
        auth_client.post(url)

        pending_action.refresh_from_db()
        assert pending_action.status == "excluded"

    def test_exclusion_clears_retries(self, auth_client, supervised_account, subscriber, pending_action):
        failure = pending_action.failure
        failure.next_retry_at = timezone.now()
        failure.save()

        url = f"/api/v1/subscribers/{subscriber.id}/exclude/"
        auth_client.post(url)

        failure.refresh_from_db()
        assert failure.next_retry_at is None

    def test_exclusion_writes_audit_event(self, auth_client, supervised_account, subscriber, pending_action):
        url = f"/api/v1/subscribers/{subscriber.id}/exclude/"
        auth_client.post(url)

        log = AuditLog.objects.filter(action="subscriber_excluded").first()
        assert log is not None
        assert log.actor == "client"

    def test_exclusion_not_found(self, auth_client, supervised_account):
        response = auth_client.post("/api/v1/subscribers/99999/exclude/")
        assert response.status_code == 404

    def test_tenant_isolation_exclusion(self, auth_client, supervised_account, subscriber):
        """Cannot exclude another account's subscriber."""
        other_user = User.objects.create_user(
            username="other2", email="other2@example.com", password="pass123"
        )
        other_sub = Subscriber.objects.create(
            account=other_user.account,
            stripe_customer_id="cus_other2",
        )

        response = auth_client.post(f"/api/v1/subscribers/{other_sub.id}/exclude/")
        assert response.status_code == 404


@pytest.mark.django_db
class TestPendingCountInDashboard:
    URL = "/api/v1/dashboard/summary/"

    @pytest.fixture
    def supervised_account(self, account):
        account.tier = "mid"
        account.dpa_accepted_at = timezone.now()
        account.engine_mode = "supervised"
        account.save()
        return account

    @pytest.fixture
    def pending_action(self, supervised_account):
        subscriber = Subscriber.objects.create(
            account=supervised_account,
            stripe_customer_id="cus_dash",
            email="dash@example.com",
        )
        failure = SubscriberFailure.objects.create(
            account=supervised_account,
            subscriber=subscriber,
            payment_intent_id="pi_dash_001",
            decline_code="insufficient_funds",
            amount_cents=1000,
            failure_created_at=timezone.now(),
            classified_action="retry_notify",
        )
        return PendingAction.objects.create(
            account=supervised_account,
            subscriber=subscriber,
            failure=failure,
            recommended_action="retry_notify",
            recommended_retry_cap=3,
            recommended_payday_aware=True,
        )

    def test_dashboard_includes_pending_count(self, auth_client, supervised_account, pending_action):
        response = auth_client.get(self.URL)
        assert response.status_code == 200
        assert response.json()["data"]["pending_action_count"] == 1

    def test_dashboard_pending_count_zero_when_none(self, auth_client, supervised_account):
        response = auth_client.get(self.URL)
        assert response.status_code == 200
        assert response.json()["data"]["pending_action_count"] == 0
