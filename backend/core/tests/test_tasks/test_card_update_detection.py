"""Tests for card-update detection and immediate retry (Story 3.3)."""
import pytest
from datetime import datetime, timezone as dt_tz
from unittest.mock import patch, MagicMock

from core.engine.state_machine import STATUS_ACTIVE, STATUS_RECOVERED
from core.models.account import TIER_MID
from core.models.subscriber import Subscriber, SubscriberFailure
from core.tasks.polling import (
    _detect_card_updates,
    _get_customer_fingerprint,
    _queue_immediate_retry,
)


@pytest.fixture
def account_autopilot(account):
    account.tier = TIER_MID
    account.dpa_accepted_at = datetime(2026, 1, 1, tzinfo=dt_tz.utc)
    account.engine_mode = "autopilot"
    account.save()
    return account


@pytest.fixture
def subscriber(account_autopilot):
    return Subscriber.objects.create(
        stripe_customer_id="cus_card_update",
        account=account_autopilot,
        last_payment_method_fingerprint="fp_old_card_123",
    )


@pytest.fixture
def subscriber_no_fingerprint(account_autopilot):
    return Subscriber.objects.create(
        stripe_customer_id="cus_no_fp",
        account=account_autopilot,
        last_payment_method_fingerprint=None,
    )


@pytest.fixture
def failure(subscriber, account_autopilot):
    return SubscriberFailure.objects.create(
        subscriber=subscriber,
        account=account_autopilot,
        payment_intent_id="pi_card_update",
        decline_code="insufficient_funds",
        amount_cents=5000,
        failure_created_at=datetime(2026, 3, 1, tzinfo=dt_tz.utc),
        classified_action="retry_notify",
        next_retry_at=datetime(2026, 3, 15, tzinfo=dt_tz.utc),
    )


def _mock_customer(fingerprint="fp_new_card_456"):
    """Build a mock Stripe Customer with invoice_settings.default_payment_method."""
    card = MagicMock()
    card.fingerprint = fingerprint
    pm = MagicMock()
    pm.card = card
    invoice_settings = MagicMock()
    invoice_settings.default_payment_method = pm
    customer = MagicMock()
    customer.invoice_settings = invoice_settings
    return customer


def _mock_customer_no_pm():
    """Mock customer with no default payment method."""
    invoice_settings = MagicMock()
    invoice_settings.default_payment_method = None
    customer = MagicMock()
    customer.invoice_settings = invoice_settings
    return customer


@pytest.mark.django_db
class TestDetectCardUpdates:

    @patch("core.tasks.retry.execute_retry")
    @patch("core.tasks.polling.stripe.Customer.retrieve")
    def test_card_update_triggers_immediate_retry(
        self, mock_retrieve, mock_execute, failure, subscriber, account_autopilot
    ):
        """AC1: Card update → immediate retry queued with correct audit metadata."""
        mock_retrieve.return_value = _mock_customer("fp_new_card_456")

        with patch("core.tasks.polling.write_audit_event") as mock_audit:
            _detect_card_updates(account_autopilot, "sk_test")

        # Fingerprint updated
        subscriber.refresh_from_db()
        assert subscriber.last_payment_method_fingerprint == "fp_new_card_456"

        # Immediate retry dispatched
        mock_execute.delay.assert_called_once_with(failure.id)

        # Failure next_retry_at set
        failure.refresh_from_db()
        assert failure.next_retry_at is not None

        # Audit event has correct metadata
        retry_calls = [c for c in mock_audit.call_args_list
                       if c.kwargs.get("action") == "retry_queued"]
        assert len(retry_calls) == 1
        meta = retry_calls[0].kwargs["metadata"]
        assert meta["trigger"] == "card_update_detected"
        assert meta["failure_id"] == str(failure.id)
        assert meta["payment_intent_id"] == failure.payment_intent_id

    @patch("core.tasks.retry.execute_retry")
    @patch("core.tasks.polling.stripe.Customer.retrieve")
    def test_same_fingerprint_no_retry(
        self, mock_retrieve, mock_execute, failure, subscriber, account_autopilot
    ):
        """Same fingerprint → no retry queued."""
        mock_retrieve.return_value = _mock_customer("fp_old_card_123")  # same as stored

        _detect_card_updates(account_autopilot, "sk_test")

        mock_execute.delay.assert_not_called()

    @patch("core.tasks.retry.execute_retry")
    @patch("core.tasks.polling.stripe.Customer.retrieve")
    def test_first_poll_null_fingerprint_no_retry(
        self, mock_retrieve, mock_execute, account_autopilot
    ):
        """AC3: First poll (null fingerprint) → fingerprint stored, no retry triggered."""
        sub = Subscriber.objects.create(
            stripe_customer_id="cus_first_poll",
            account=account_autopilot,
            last_payment_method_fingerprint=None,
        )
        SubscriberFailure.objects.create(
            subscriber=sub,
            account=account_autopilot,
            payment_intent_id="pi_first_poll",
            decline_code="insufficient_funds",
            amount_cents=1000,
            failure_created_at=datetime(2026, 1, 1, tzinfo=dt_tz.utc),
            classified_action="retry_notify",
            next_retry_at=datetime(2026, 2, 1, tzinfo=dt_tz.utc),
        )

        mock_retrieve.return_value = _mock_customer("fp_initial_123")

        _detect_card_updates(account_autopilot, "sk_test")

        sub.refresh_from_db()
        assert sub.last_payment_method_fingerprint == "fp_initial_123"
        mock_execute.delay.assert_not_called()

    @patch("core.tasks.retry.execute_retry")
    @patch("core.tasks.polling.stripe.Customer.retrieve")
    def test_subscriber_not_active_skipped(
        self, mock_retrieve, mock_execute, account_autopilot
    ):
        """Subscriber not in active status → no detection."""
        sub = Subscriber.objects.create(
            stripe_customer_id="cus_recovered",
            account=account_autopilot,
        )
        Subscriber.objects.filter(pk=sub.pk).update(status="recovered")

        _detect_card_updates(account_autopilot, "sk_test")

        mock_retrieve.assert_not_called()
        mock_execute.delay.assert_not_called()

    @patch("core.tasks.retry.execute_retry")
    @patch("core.tasks.polling.stripe.Customer.retrieve")
    def test_no_pending_failures_skipped(
        self, mock_retrieve, mock_execute, account_autopilot
    ):
        """AC3: Subscriber with no failures → no retry queued."""
        Subscriber.objects.create(
            stripe_customer_id="cus_no_failures",
            account=account_autopilot,
            last_payment_method_fingerprint="fp_something",
        )

        _detect_card_updates(account_autopilot, "sk_test")

        mock_retrieve.assert_not_called()

    @patch("core.tasks.polling.stripe.Customer.retrieve")
    def test_no_default_payment_method_skipped(
        self, mock_retrieve, failure, subscriber, account_autopilot
    ):
        """Edge case: no default payment method → skip detection."""
        mock_retrieve.return_value = _mock_customer_no_pm()

        _detect_card_updates(account_autopilot, "sk_test")

        subscriber.refresh_from_db()
        assert subscriber.last_payment_method_fingerprint == "fp_old_card_123"  # unchanged

    @patch("core.tasks.retry.execute_retry")
    @patch("core.tasks.polling.stripe.Customer.retrieve")
    def test_stripe_error_continues_gracefully(
        self, mock_retrieve, mock_execute, failure, subscriber, account_autopilot
    ):
        """Stripe API error → gracefully skipped, poll continues."""
        import stripe as stripe_mod
        mock_retrieve.side_effect = stripe_mod.StripeError("rate limited")

        # Should not raise
        _detect_card_updates(account_autopilot, "sk_test")

        mock_execute.delay.assert_not_called()


@pytest.mark.django_db
class TestGetCustomerFingerprint:

    @patch("core.tasks.polling.stripe.Customer.retrieve")
    def test_returns_fingerprint(self, mock_retrieve, subscriber):
        mock_retrieve.return_value = _mock_customer("fp_test_123")
        result = _get_customer_fingerprint(subscriber, "sk_test")
        assert result == "fp_test_123"

    @patch("core.tasks.polling.stripe.Customer.retrieve")
    def test_no_default_pm_returns_none(self, mock_retrieve, subscriber):
        mock_retrieve.return_value = _mock_customer_no_pm()
        result = _get_customer_fingerprint(subscriber, "sk_test")
        assert result is None

    @patch("core.tasks.polling.stripe.Customer.retrieve")
    def test_no_card_returns_none(self, mock_retrieve, subscriber):
        pm = MagicMock(spec=[])  # no card attribute
        invoice_settings = MagicMock()
        invoice_settings.default_payment_method = pm
        customer = MagicMock()
        customer.invoice_settings = invoice_settings
        mock_retrieve.return_value = customer

        result = _get_customer_fingerprint(subscriber, "sk_test")
        assert result is None


@pytest.mark.django_db
class TestQueueImmediateRetry:

    @patch("core.tasks.retry.execute_retry")
    def test_queues_most_recent_failure(self, mock_execute, subscriber, account_autopilot):
        """Queues retry for most recent failure by failure_created_at."""
        old_failure = SubscriberFailure.objects.create(
            subscriber=subscriber,
            account=account_autopilot,
            payment_intent_id="pi_old",
            decline_code="insufficient_funds",
            amount_cents=1000,
            failure_created_at=datetime(2026, 1, 1, tzinfo=dt_tz.utc),
            classified_action="retry_notify",
        )
        new_failure = SubscriberFailure.objects.create(
            subscriber=subscriber,
            account=account_autopilot,
            payment_intent_id="pi_new",
            decline_code="insufficient_funds",
            amount_cents=2000,
            failure_created_at=datetime(2026, 3, 1, tzinfo=dt_tz.utc),
            classified_action="retry_notify",
        )

        with patch("core.tasks.polling.write_audit_event"):
            _queue_immediate_retry(subscriber, account_autopilot)

        mock_execute.delay.assert_called_once_with(new_failure.id)
        new_failure.refresh_from_db()
        assert new_failure.next_retry_at is not None


@pytest.mark.django_db
class TestFingerprintPopulationOnIngestion:

    def test_fingerprint_set_on_first_ingestion(self, account):
        """Fingerprint populated from payment intent charges on first ingestion."""
        from core.services.failure_ingestion import ingest_failed_payment

        pi = MagicMock()
        pi.id = "pi_fp_test"
        pi.customer = "cus_fp_test"
        pi.amount = 1000
        pi.created = 1704067200  # 2024-01-01 UTC

        error = MagicMock()
        error.decline_code = "insufficient_funds"
        pi.last_payment_error = error

        card = MagicMock()
        card.country = "US"
        card.fingerprint = "fp_from_charge"
        pm_details = MagicMock()
        pm_details.card = card
        billing = MagicMock()
        billing.email = "test@example.com"
        charge = MagicMock()
        charge.billing_details = billing
        charge.payment_method_details = pm_details
        charges = MagicMock()
        charges.data = [charge]
        pi.charges = charges

        subscriber, failure, created = ingest_failed_payment(account, pi)
        assert subscriber.last_payment_method_fingerprint == "fp_from_charge"

    def test_fingerprint_not_overwritten_on_subsequent_ingestion(self, account):
        """Existing fingerprint is not overwritten on subsequent ingestion."""
        from core.services.failure_ingestion import ingest_failed_payment

        # Create subscriber with existing fingerprint
        sub = Subscriber.objects.create(
            stripe_customer_id="cus_fp_existing",
            account=account,
            last_payment_method_fingerprint="fp_original",
        )

        pi = MagicMock()
        pi.id = "pi_fp_existing"
        pi.customer = "cus_fp_existing"
        pi.amount = 1000
        pi.created = 1704067200

        error = MagicMock()
        error.decline_code = "insufficient_funds"
        pi.last_payment_error = error

        card = MagicMock()
        card.country = "US"
        card.fingerprint = "fp_new_from_charge"
        pm_details = MagicMock()
        pm_details.card = card
        billing = MagicMock()
        billing.email = None
        charge = MagicMock()
        charge.billing_details = billing
        charge.payment_method_details = pm_details
        charges = MagicMock()
        charges.data = [charge]
        pi.charges = charges

        subscriber, failure, created = ingest_failed_payment(account, pi)
        subscriber.refresh_from_db()
        assert subscriber.last_payment_method_fingerprint == "fp_original"  # not overwritten
