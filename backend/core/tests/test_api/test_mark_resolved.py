"""Story 3.3 v1 — tests for POST /api/v1/subscribers/{id}/mark-resolved/."""
import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.engine.state_machine import (
    STATUS_ACTIVE,
    STATUS_FRAUD_FLAGGED,
    STATUS_PASSIVE_CHURN,
    STATUS_RECOVERED,
)
from core.models.audit import AuditLog
from core.models.subscriber import Subscriber
from core.services.dpa import CURRENT_DPA_VERSION


URL_TEMPLATE = "/api/v1/subscribers/{id}/mark-resolved/"


@pytest.fixture
def mid_account_with_dpa(account):
    account.tier = "mid"
    account.dpa_accepted_at = timezone.now()
    account.dpa_version = CURRENT_DPA_VERSION
    account.save(update_fields=["tier", "dpa_accepted_at", "dpa_version"])
    return account


def _make_subscriber(account, status=STATUS_ACTIVE, suffix=""):
    return Subscriber.objects.create(
        stripe_customer_id=f"cus_test_mr{suffix}",
        email=f"alice{suffix}@example.com",
        status=status,
        account=account,
    )


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
class TestMarkResolvedEndpoint:
    def test_requires_authentication(self, client):
        response = client.post(URL_TEMPLATE.format(id=1))
        assert response.status_code == 401

    def test_dpa_required_returns_403(self, auth_client, account):
        account.tier = "mid"
        account.save(update_fields=["tier"])
        response = auth_client.post(URL_TEMPLATE.format(id=1), format="json")
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "DPA_REQUIRED"

    def test_free_tier_returns_403(self, auth_client, account):
        account.tier = "free"
        account.dpa_accepted_at = timezone.now()
        account.dpa_version = CURRENT_DPA_VERSION
        account.save(update_fields=["tier", "dpa_accepted_at", "dpa_version"])
        response = auth_client.post(URL_TEMPLATE.format(id=1), format="json")
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "TIER_REQUIRED"

    def test_subscriber_not_found_returns_404(self, auth_client, mid_account_with_dpa):
        response = auth_client.post(URL_TEMPLATE.format(id=99999), format="json")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND"

    def test_resolves_active_subscriber(self, auth_client, mid_account_with_dpa):
        sub = _make_subscriber(mid_account_with_dpa, status=STATUS_ACTIVE)
        response = auth_client.post(URL_TEMPLATE.format(id=sub.id), format="json")
        assert response.status_code == 200
        body = response.json()["data"]
        assert body == {
            "resolved": True,
            "subscriber_id": sub.id,
            "from_status": STATUS_ACTIVE,
            "to_status": "recovered",
        }
        sub.refresh_from_db()
        assert sub.status == STATUS_RECOVERED
        # Two audit rows: status_recovered (FSM signal) + manual_resolved (view)
        audits = list(AuditLog.objects.filter(subscriber_id=str(sub.id)))
        actions = [a.action for a in audits]
        assert "status_recovered" in actions
        assert "manual_resolved" in actions
        manual = next(a for a in audits if a.action == "manual_resolved")
        assert manual.actor == "client"
        assert manual.metadata["from"] == STATUS_ACTIVE
        assert manual.metadata["trigger"] == "client_manual"

    def test_resolves_passive_churn_subscriber(self, auth_client, mid_account_with_dpa):
        sub = _make_subscriber(mid_account_with_dpa, status=STATUS_ACTIVE, suffix="_pc")
        # Force passive_churn via direct .update() to bypass FSM source check.
        Subscriber.objects.filter(pk=sub.pk).update(status=STATUS_PASSIVE_CHURN)
        sub.refresh_from_db()
        response = auth_client.post(URL_TEMPLATE.format(id=sub.id), format="json")
        assert response.status_code == 200
        sub.refresh_from_db()
        assert sub.status == STATUS_RECOVERED
        manual = AuditLog.objects.filter(
            subscriber_id=str(sub.id), action="manual_resolved"
        ).first()
        assert manual is not None
        assert manual.metadata["from"] == STATUS_PASSIVE_CHURN

    def test_resolves_fraud_flagged_subscriber(self, auth_client, mid_account_with_dpa):
        sub = _make_subscriber(mid_account_with_dpa, status=STATUS_ACTIVE, suffix="_ff")
        Subscriber.objects.filter(pk=sub.pk).update(status=STATUS_FRAUD_FLAGGED)
        sub.refresh_from_db()
        response = auth_client.post(URL_TEMPLATE.format(id=sub.id), format="json")
        assert response.status_code == 200
        sub.refresh_from_db()
        assert sub.status == STATUS_RECOVERED
        manual = AuditLog.objects.filter(
            subscriber_id=str(sub.id), action="manual_resolved"
        ).first()
        assert manual is not None
        assert manual.metadata["from"] == STATUS_FRAUD_FLAGGED

    def test_already_recovered_returns_400(self, auth_client, mid_account_with_dpa):
        sub = _make_subscriber(mid_account_with_dpa, status=STATUS_ACTIVE, suffix="_rec")
        Subscriber.objects.filter(pk=sub.pk).update(status=STATUS_RECOVERED)
        before_audit_count = AuditLog.objects.filter(subscriber_id=str(sub.id)).count()
        response = auth_client.post(URL_TEMPLATE.format(id=sub.id), format="json")
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "INVALID_TRANSITION"
        sub.refresh_from_db()
        assert sub.status == STATUS_RECOVERED  # unchanged
        after_audit_count = AuditLog.objects.filter(subscriber_id=str(sub.id)).count()
        assert after_audit_count == before_audit_count  # no audit row added

    def test_tenant_isolation(self, auth_client, mid_account_with_dpa, second_account):
        other_sub = Subscriber.objects.create(
            stripe_customer_id="cus_other_mr",
            email="other_mr@example.com",
            status=STATUS_ACTIVE,
            account=second_account,
        )
        response = auth_client.post(URL_TEMPLATE.format(id=other_sub.id), format="json")
        assert response.status_code == 404
        other_sub.refresh_from_db()
        assert other_sub.status == STATUS_ACTIVE
