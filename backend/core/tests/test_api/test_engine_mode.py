from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from core.models.account import Account
from core.models.audit import AuditLog
from core.models.pending_action import PendingAction, STATUS_PENDING
from core.models.subscriber import Subscriber, SubscriberFailure


@pytest.mark.django_db
class TestSetEngineMode:
    URL = "/api/v1/account/engine/mode/"

    @pytest.fixture
    def mid_account_with_dpa(self, account):
        account.tier = "mid"
        account.dpa_accepted_at = timezone.now()
        account.save()
        return account

    def test_first_activation_autopilot(self, auth_client, mid_account_with_dpa):
        response = auth_client.post(self.URL, {"mode": "autopilot"}, format="json")
        assert response.status_code == 200

        data = response.json()["data"]
        assert data["engine_mode"] == "autopilot"
        assert data["engine_active"] is True

        log = AuditLog.objects.filter(action="engine_activated").first()
        assert log is not None
        assert log.metadata == {"mode": "autopilot"}

    def test_first_activation_supervised(self, auth_client, mid_account_with_dpa):
        response = auth_client.post(self.URL, {"mode": "supervised"}, format="json")
        assert response.status_code == 200

        data = response.json()["data"]
        assert data["engine_mode"] == "supervised"

        log = AuditLog.objects.filter(action="engine_activated").first()
        assert log is not None
        assert log.metadata == {"mode": "supervised"}

    def test_mode_switch_creates_switch_audit(self, auth_client, mid_account_with_dpa):
        mid_account_with_dpa.engine_mode = "autopilot"
        mid_account_with_dpa.save()

        response = auth_client.post(self.URL, {"mode": "supervised"}, format="json")
        assert response.status_code == 200

        data = response.json()["data"]
        assert data["engine_mode"] == "supervised"

        log = AuditLog.objects.filter(action="engine_mode_switched").first()
        assert log is not None
        assert log.metadata == {"from": "autopilot", "to": "supervised"}

    def test_same_mode_idempotent(self, auth_client, mid_account_with_dpa):
        mid_account_with_dpa.engine_mode = "autopilot"
        mid_account_with_dpa.save()

        response = auth_client.post(self.URL, {"mode": "autopilot"}, format="json")
        assert response.status_code == 200

        assert AuditLog.objects.filter(action="engine_activated").count() == 0
        assert AuditLog.objects.filter(action="engine_mode_switched").count() == 0

    def test_rejected_without_dpa(self, auth_client, account):
        account.tier = "mid"
        account.save()

        response = auth_client.post(self.URL, {"mode": "autopilot"}, format="json")
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "DPA_NOT_ACCEPTED"

    def test_rejected_for_free_tier(self, auth_client, account):
        account.tier = "free"
        account.dpa_accepted_at = timezone.now()
        account.save()

        response = auth_client.post(self.URL, {"mode": "autopilot"}, format="json")
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "TIER_NOT_ELIGIBLE"

    def test_invalid_mode_rejected(self, auth_client, mid_account_with_dpa):
        response = auth_client.post(self.URL, {"mode": "invalid"}, format="json")
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "INVALID_MODE"

    def test_missing_mode_rejected(self, auth_client, mid_account_with_dpa):
        response = auth_client.post(self.URL, {}, format="json")
        assert response.status_code == 400

    def test_requires_authentication(self, db):
        client = APIClient()
        response = client.post(self.URL, {"mode": "autopilot"}, format="json")
        assert response.status_code == 401

    def test_response_includes_all_account_fields(self, auth_client, mid_account_with_dpa):
        response = auth_client.post(self.URL, {"mode": "autopilot"}, format="json")
        data = response.json()["data"]

        assert "id" in data
        assert "owner" in data
        assert "tier" in data
        assert "dpa_accepted" in data
        assert "engine_mode" in data
        assert "engine_active" in data


@pytest.mark.django_db
class TestEngineActivationBackfill:
    """Verify that recent unprocessed failures are backfilled on engine activation."""

    URL = "/api/v1/account/engine/mode/"

    @pytest.fixture
    def mid_account_with_dpa(self, account):
        account.tier = "mid"
        account.dpa_accepted_at = timezone.now()
        account.save()
        return account

    @pytest.fixture
    def subscriber_with_failure(self, mid_account_with_dpa):
        sub = Subscriber.objects.create(
            account=mid_account_with_dpa,
            stripe_customer_id="cus_test_backfill",
            email="backfill@example.com",
        )
        failure = SubscriberFailure.objects.create(
            account=mid_account_with_dpa,
            subscriber=sub,
            payment_intent_id="pi_backfill_1",
            decline_code="insufficient_funds",
            amount_cents=5000,
            failure_created_at=timezone.now() - timedelta(hours=2),
            classified_action="retry_notify",
        )
        return sub, failure

    def test_supervised_activation_backfills_recent_failures(
        self, auth_client, mid_account_with_dpa, subscriber_with_failure
    ):
        """Failures ingested before engine activation should appear in the supervised queue."""
        sub, failure = subscriber_with_failure

        assert PendingAction.objects.count() == 0

        response = auth_client.post(self.URL, {"mode": "supervised"}, format="json")
        assert response.status_code == 200

        actions = PendingAction.objects.filter(status=STATUS_PENDING)
        assert actions.count() == 1
        assert actions.first().failure_id == failure.id
        assert actions.first().subscriber_id == sub.id

    def test_backfill_skips_failures_older_than_24h(
        self, auth_client, mid_account_with_dpa
    ):
        sub = Subscriber.objects.create(
            account=mid_account_with_dpa,
            stripe_customer_id="cus_test_old",
            email="old@example.com",
        )
        SubscriberFailure.objects.create(
            account=mid_account_with_dpa,
            subscriber=sub,
            payment_intent_id="pi_old_1",
            decline_code="insufficient_funds",
            amount_cents=3000,
            failure_created_at=timezone.now() - timedelta(hours=25),
            classified_action="retry_notify",
        )

        response = auth_client.post(self.URL, {"mode": "supervised"}, format="json")
        assert response.status_code == 200
        assert PendingAction.objects.count() == 0

    def test_backfill_skips_excluded_subscribers(
        self, auth_client, mid_account_with_dpa
    ):
        sub = Subscriber.objects.create(
            account=mid_account_with_dpa,
            stripe_customer_id="cus_excluded",
            email="excluded@example.com",
            excluded_from_automation=True,
        )
        SubscriberFailure.objects.create(
            account=mid_account_with_dpa,
            subscriber=sub,
            payment_intent_id="pi_excluded_1",
            decline_code="insufficient_funds",
            amount_cents=4000,
            failure_created_at=timezone.now() - timedelta(hours=1),
            classified_action="retry_notify",
        )

        response = auth_client.post(self.URL, {"mode": "supervised"}, format="json")
        assert response.status_code == 200
        assert PendingAction.objects.count() == 0

    def test_backfill_skips_already_queued_failures(
        self, auth_client, mid_account_with_dpa, subscriber_with_failure
    ):
        """Failures that already have a pending action should not be duplicated."""
        sub, failure = subscriber_with_failure

        PendingAction.objects.create(
            account=mid_account_with_dpa,
            subscriber=sub,
            failure=failure,
            recommended_action="retry_notify",
            recommended_retry_cap=3,
            recommended_payday_aware=True,
        )

        response = auth_client.post(self.URL, {"mode": "supervised"}, format="json")
        assert response.status_code == 200
        assert PendingAction.objects.filter(status=STATUS_PENDING).count() == 1

    def test_backfill_creates_audit_event(
        self, auth_client, mid_account_with_dpa, subscriber_with_failure
    ):
        response = auth_client.post(self.URL, {"mode": "supervised"}, format="json")
        assert response.status_code == 200

        log = AuditLog.objects.filter(action="action_queued_supervised").first()
        assert log is not None
        assert log.metadata["trigger"] == "engine_activation_backfill"
