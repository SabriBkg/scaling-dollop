"""Tests for Subscriber FSM transitions (django-fsm)."""
import pytest
from unittest.mock import patch

from django_fsm import TransitionNotAllowed

from core.engine.state_machine import (
    STATUS_ACTIVE,
    STATUS_RECOVERED,
    STATUS_PASSIVE_CHURN,
    STATUS_FRAUD_FLAGGED,
)
from core.models.subscriber import Subscriber


@pytest.mark.django_db
class TestSubscriberFSMTransitions:
    """Test valid and invalid FSM transitions on Subscriber.status."""

    def _make_subscriber(self, account, status=STATUS_ACTIVE):
        sub = Subscriber.objects.create(
            stripe_customer_id="cus_fsm_test",
            account=account,
        )
        if status != STATUS_ACTIVE:
            sub.status = status
            Subscriber.objects.filter(pk=sub.pk).update(status=status)
            sub.refresh_from_db()
        return sub

    # --- Valid transitions ---

    def test_active_to_recovered(self, account):
        sub = self._make_subscriber(account)
        sub.recover()
        sub.save()
        sub.refresh_from_db()
        assert sub.status == STATUS_RECOVERED

    def test_active_to_passive_churn(self, account):
        sub = self._make_subscriber(account)
        sub.mark_passive_churn()
        sub.save()
        sub.refresh_from_db()
        assert sub.status == STATUS_PASSIVE_CHURN

    def test_active_to_fraud_flagged(self, account):
        sub = self._make_subscriber(account)
        sub.mark_fraud_flagged()
        sub.save()
        sub.refresh_from_db()
        assert sub.status == STATUS_FRAUD_FLAGGED

    # --- Invalid transitions ---

    def test_recovered_cannot_recover_again(self, account):
        sub = self._make_subscriber(account, status=STATUS_RECOVERED)
        with pytest.raises(TransitionNotAllowed):
            sub.recover()

    def test_recovered_cannot_mark_passive_churn(self, account):
        sub = self._make_subscriber(account, status=STATUS_RECOVERED)
        with pytest.raises(TransitionNotAllowed):
            sub.mark_passive_churn()

    def test_recovered_cannot_mark_fraud_flagged(self, account):
        sub = self._make_subscriber(account, status=STATUS_RECOVERED)
        with pytest.raises(TransitionNotAllowed):
            sub.mark_fraud_flagged()

    def test_passive_churn_cannot_recover(self, account):
        sub = self._make_subscriber(account, status=STATUS_PASSIVE_CHURN)
        with pytest.raises(TransitionNotAllowed):
            sub.recover()

    def test_fraud_flagged_cannot_recover(self, account):
        sub = self._make_subscriber(account, status=STATUS_FRAUD_FLAGGED)
        with pytest.raises(TransitionNotAllowed):
            sub.recover()

    def test_fraud_flagged_cannot_mark_passive_churn(self, account):
        sub = self._make_subscriber(account, status=STATUS_FRAUD_FLAGGED)
        with pytest.raises(TransitionNotAllowed):
            sub.mark_passive_churn()


@pytest.mark.django_db
class TestSubscriberFSMPostTransitionSignal:
    """Test that post-transition signal fires write_audit_event."""

    def test_recover_writes_audit_event(self, account):
        sub = Subscriber.objects.create(
            stripe_customer_id="cus_signal_test",
            account=account,
        )
        with patch("core.services.audit.write_audit_event") as mock_audit:
            sub.recover()
            sub.save()

            mock_audit.assert_called_once_with(
                subscriber=str(sub.id),
                actor="engine",
                action="status_recovered",
                outcome="success",
                metadata={"from": STATUS_ACTIVE, "to": STATUS_RECOVERED},
                account=sub.account,
            )

    def test_mark_passive_churn_writes_audit_event(self, account):
        sub = Subscriber.objects.create(
            stripe_customer_id="cus_signal_churn",
            account=account,
        )
        with patch("core.services.audit.write_audit_event") as mock_audit:
            sub.mark_passive_churn()
            sub.save()

            mock_audit.assert_called_once_with(
                subscriber=str(sub.id),
                actor="engine",
                action="status_passive_churn",
                outcome="success",
                metadata={"from": STATUS_ACTIVE, "to": STATUS_PASSIVE_CHURN},
                account=sub.account,
            )

    def test_mark_fraud_flagged_writes_audit_event(self, account):
        sub = Subscriber.objects.create(
            stripe_customer_id="cus_signal_fraud",
            account=account,
        )
        with patch("core.services.audit.write_audit_event") as mock_audit:
            sub.mark_fraud_flagged()
            sub.save()

            mock_audit.assert_called_once_with(
                subscriber=str(sub.id),
                actor="engine",
                action="status_fraud_flagged",
                outcome="success",
                metadata={"from": STATUS_ACTIVE, "to": STATUS_FRAUD_FLAGGED},
                account=sub.account,
            )
