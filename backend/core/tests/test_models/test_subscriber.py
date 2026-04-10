"""Tests for Subscriber and SubscriberFailure models."""
import pytest
from datetime import datetime, timezone as dt_tz

from django.contrib.auth.models import User
from django.db import IntegrityError

from core.models.subscriber import Subscriber, SubscriberFailure


@pytest.mark.django_db
class TestSubscriber:
    def test_inherits_tenant_scoped_model(self):
        """Subscriber extends TenantScopedModel — has account FK, created_at, updated_at."""
        assert hasattr(Subscriber, "account")
        assert hasattr(Subscriber, "created_at")
        assert hasattr(Subscriber, "updated_at")

    def test_for_account_query(self, account):
        """Subscriber.objects.for_account() filters by account."""
        sub = Subscriber.objects.create(
            stripe_customer_id="cus_123",
            email="test@example.com",
            account=account,
        )
        found = Subscriber.objects.for_account(account.id)
        assert sub in found

    def test_unique_constraint_per_account(self, account):
        """Cannot create duplicate stripe_customer_id for same account."""
        Subscriber.objects.create(
            stripe_customer_id="cus_dup",
            email="a@example.com",
            account=account,
        )
        with pytest.raises(IntegrityError):
            Subscriber.objects.create(
                stripe_customer_id="cus_dup",
                email="b@example.com",
                account=account,
            )

    def test_different_accounts_same_customer_id(self, account):
        """Same stripe_customer_id allowed across different accounts."""
        user2 = User.objects.create_user(username="other", email="other@example.com", password="pass")
        account2 = user2.account

        Subscriber.objects.create(stripe_customer_id="cus_shared", account=account)
        Subscriber.objects.create(stripe_customer_id="cus_shared", account=account2)
        assert Subscriber.objects.filter(stripe_customer_id="cus_shared").count() == 2

    def test_default_status_active(self, account):
        sub = Subscriber.objects.create(stripe_customer_id="cus_active", account=account)
        assert sub.status == "active"


@pytest.mark.django_db
class TestSubscriberFailure:
    def test_payment_intent_id_unique(self, account):
        """payment_intent_id must be globally unique."""
        sub = Subscriber.objects.create(stripe_customer_id="cus_f1", account=account)
        SubscriberFailure.objects.create(
            subscriber=sub,
            account=account,
            payment_intent_id="pi_unique",
            decline_code="insufficient_funds",
            amount_cents=1000,
            failure_created_at=datetime(2026, 1, 1, tzinfo=dt_tz.utc),
            classified_action="retry_notify",
        )
        with pytest.raises(IntegrityError):
            SubscriberFailure.objects.create(
                subscriber=sub,
                account=account,
                payment_intent_id="pi_unique",
                decline_code="expired_card",
                amount_cents=2000,
                failure_created_at=datetime(2026, 1, 2, tzinfo=dt_tz.utc),
                classified_action="notify_only",
            )

    def test_inherits_tenant_scoped_model(self):
        assert hasattr(SubscriberFailure, "account")
        assert hasattr(SubscriberFailure, "created_at")
        assert hasattr(SubscriberFailure, "updated_at")

    def test_nullable_country(self, account):
        """payment_method_country is nullable."""
        sub = Subscriber.objects.create(stripe_customer_id="cus_f2", account=account)
        failure = SubscriberFailure.objects.create(
            subscriber=sub,
            account=account,
            payment_intent_id="pi_no_country",
            decline_code="generic_decline",
            amount_cents=500,
            failure_created_at=datetime(2026, 1, 1, tzinfo=dt_tz.utc),
            classified_action="retry_notify",
            payment_method_country=None,
        )
        assert failure.payment_method_country is None

    def test_for_account_query(self, account):
        sub = Subscriber.objects.create(stripe_customer_id="cus_f3", account=account)
        failure = SubscriberFailure.objects.create(
            subscriber=sub,
            account=account,
            payment_intent_id="pi_tenant",
            decline_code="expired_card",
            amount_cents=100,
            failure_created_at=datetime(2026, 1, 1, tzinfo=dt_tz.utc),
            classified_action="notify_only",
        )
        found = SubscriberFailure.objects.for_account(account.id)
        assert failure in found
