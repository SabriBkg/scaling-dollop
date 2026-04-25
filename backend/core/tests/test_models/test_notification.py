"""Tests for NotificationLog and NotificationOptOut models."""
import pytest
from unittest.mock import patch

from cryptography.fernet import Fernet
from django.db import IntegrityError
from django.utils import timezone

from core.models.account import StripeConnection, TIER_MID
from core.models.notification import NotificationLog, NotificationOptOut
from core.models.subscriber import Subscriber, SubscriberFailure


@pytest.fixture(autouse=True)
def _fernet_key():
    key = Fernet.generate_key().decode()
    with patch.dict("os.environ", {"STRIPE_TOKEN_KEY": key}):
        from core.services import encryption
        encryption._cipher = None
        yield
        encryption._cipher = None


@pytest.fixture
def mid_account(account):
    account.tier = TIER_MID
    account.company_name = "TestCo"
    account.save()
    conn = StripeConnection(account=account, stripe_user_id="acct_model_test")
    conn.access_token = "sk_test"
    conn.save()
    return account


@pytest.fixture
def subscriber(mid_account):
    return Subscriber.objects.create(
        account=mid_account,
        stripe_customer_id="cus_model_test",
        email="model@example.com",
    )


@pytest.fixture
def failure(mid_account, subscriber):
    return SubscriberFailure.objects.create(
        account=mid_account,
        subscriber=subscriber,
        payment_intent_id="pi_model_test",
        decline_code="insufficient_funds",
        amount_cents=1000,
        failure_created_at=timezone.now(),
        classified_action="retry_notify",
    )


@pytest.mark.django_db
class TestNotificationLog:
    def test_create(self, mid_account, subscriber, failure):
        log = NotificationLog.objects.create(
            account=mid_account,
            subscriber=subscriber,
            failure=failure,
            email_type="failure_notice",
            resend_message_id="msg_test",
            status="sent",
        )
        assert log.id is not None
        assert log.email_type == "failure_notice"
        assert log.status == "sent"
        assert log.resend_message_id == "msg_test"

    def test_nullable_failure(self, mid_account, subscriber):
        log = NotificationLog.objects.create(
            account=mid_account,
            subscriber=subscriber,
            failure=None,
            email_type="failure_notice",
            status="suppressed",
        )
        assert log.failure is None

    def test_tenant_scoping(self, mid_account, subscriber, failure):
        NotificationLog.objects.create(
            account=mid_account,
            subscriber=subscriber,
            failure=failure,
            email_type="failure_notice",
            status="sent",
        )
        assert NotificationLog.objects.for_account(mid_account.id).count() == 1
        assert NotificationLog.objects.for_account(99999).count() == 0

    def test_metadata_default(self, mid_account, subscriber, failure):
        log = NotificationLog.objects.create(
            account=mid_account,
            subscriber=subscriber,
            failure=failure,
            email_type="failure_notice",
            status="sent",
        )
        assert log.metadata == {}


@pytest.mark.django_db
class TestNotificationOptOut:
    def test_create(self, mid_account):
        opt_out = NotificationOptOut.objects.create(
            account=mid_account,
            subscriber_email="optout@example.com",
        )
        assert opt_out.id is not None

    def test_unique_per_account(self, mid_account):
        NotificationOptOut.objects.create(
            account=mid_account,
            subscriber_email="dup@example.com",
        )
        with pytest.raises(IntegrityError):
            NotificationOptOut.objects.create(
                account=mid_account,
                subscriber_email="dup@example.com",
            )

    def test_tenant_scoping(self, mid_account):
        NotificationOptOut.objects.create(
            account=mid_account,
            subscriber_email="scoped@example.com",
        )
        assert NotificationOptOut.objects.for_account(mid_account.id).count() == 1
        assert NotificationOptOut.objects.for_account(99999).count() == 0
