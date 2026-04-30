"""Story 3.3 v1 — Subscriber.mark_resolved_manually() FSM unit tests."""
import pytest
from django_fsm import TransitionNotAllowed

from core.engine.state_machine import (
    STATUS_ACTIVE,
    STATUS_FRAUD_FLAGGED,
    STATUS_PASSIVE_CHURN,
    STATUS_RECOVERED,
)
from core.models.subscriber import Subscriber


@pytest.mark.django_db
class TestMarkResolvedManually:
    def _make(self, account, status):
        return Subscriber.objects.create(
            stripe_customer_id=f"cus_fsm_{status}",
            email=f"sub_{status}@example.com",
            status=status,
            account=account,
        )

    def test_from_active(self, account):
        sub = self._make(account, STATUS_ACTIVE)
        sub.mark_resolved_manually()
        sub.save()
        sub.refresh_from_db()
        assert sub.status == STATUS_RECOVERED

    def test_from_passive_churn(self, account):
        sub = self._make(account, STATUS_ACTIVE)
        Subscriber.objects.filter(pk=sub.pk).update(status=STATUS_PASSIVE_CHURN)
        sub.refresh_from_db()
        sub.mark_resolved_manually()
        sub.save()
        sub.refresh_from_db()
        assert sub.status == STATUS_RECOVERED

    def test_from_fraud_flagged(self, account):
        sub = self._make(account, STATUS_ACTIVE)
        Subscriber.objects.filter(pk=sub.pk).update(status=STATUS_FRAUD_FLAGGED)
        sub.refresh_from_db()
        sub.mark_resolved_manually()
        sub.save()
        sub.refresh_from_db()
        assert sub.status == STATUS_RECOVERED

    def test_from_recovered_raises(self, account):
        sub = self._make(account, STATUS_ACTIVE)
        Subscriber.objects.filter(pk=sub.pk).update(status=STATUS_RECOVERED)
        sub.refresh_from_db()
        with pytest.raises(TransitionNotAllowed):
            sub.mark_resolved_manually()
