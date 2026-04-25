"""Tests for the notification Celery task."""
import pytest
from unittest.mock import patch, MagicMock

from cryptography.fernet import Fernet

from core.models.audit import AuditLog
from core.models.dead_letter import DeadLetterLog
from core.models.notification import NotificationLog, NotificationOptOut
from core.models.subscriber import Subscriber, SubscriberFailure
from core.models.account import StripeConnection, TIER_MID, TIER_FREE
from core.tasks.notifications import send_failure_notification


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
    """Account configured as Mid tier with DPA and engine mode."""
    from django.utils import timezone
    account.tier = TIER_MID
    account.dpa_accepted_at = timezone.now()
    account.engine_mode = "autopilot"
    account.company_name = "TestCo"
    account.save()

    conn = StripeConnection(account=account, stripe_user_id="acct_test")
    conn.access_token = "sk_test"
    conn.save()

    return account


@pytest.fixture
def subscriber_with_email(mid_account):
    return Subscriber.objects.create(
        account=mid_account,
        stripe_customer_id="cus_test",
        email="user@example.com",
    )


@pytest.fixture
def failure(mid_account, subscriber_with_email):
    from django.utils import timezone
    return SubscriberFailure.objects.create(
        account=mid_account,
        subscriber=subscriber_with_email,
        payment_intent_id="pi_test_notify",
        decline_code="insufficient_funds",
        amount_cents=2000,
        failure_created_at=timezone.now(),
        classified_action="retry_notify",
    )


@pytest.mark.django_db
class TestSendFailureNotification:
    @patch("core.tasks.notifications.send_notification_email")
    def test_success_path(self, mock_send, failure):
        """Successful send creates NotificationLog and audit event."""
        mock_send.return_value = "msg_123"

        send_failure_notification(failure.id)

        assert NotificationLog.objects.filter(status="sent").count() == 1
        log = NotificationLog.objects.get(status="sent")
        assert log.resend_message_id == "msg_123"
        assert log.email_type == "failure_notice"
        assert log.failure == failure

        audit = AuditLog.objects.filter(action="notification_sent").first()
        assert audit is not None
        assert audit.outcome == "success"
        assert audit.metadata["resend_message_id"] == "msg_123"

    @patch("core.tasks.notifications.send_notification_email")
    def test_free_tier_suppressed(self, mock_send, failure):
        """Free-tier accounts should be suppressed (engine not active)."""
        account = failure.account
        account.tier = TIER_FREE
        account.save()

        send_failure_notification(failure.id)

        mock_send.assert_not_called()
        assert NotificationLog.objects.filter(status="suppressed").count() == 1
        log = NotificationLog.objects.get(status="suppressed")
        assert log.metadata["reason"] == "engine_not_active"

    @patch("core.tasks.notifications.send_notification_email")
    def test_no_dpa_suppressed(self, mock_send, failure):
        """Account without DPA should be suppressed."""
        account = failure.account
        account.dpa_accepted_at = None
        account.save()

        send_failure_notification(failure.id)

        mock_send.assert_not_called()
        assert NotificationLog.objects.filter(status="suppressed").count() == 1

    @patch("core.tasks.notifications.send_notification_email")
    def test_no_email_skipped(self, mock_send, failure):
        """Subscriber with no email should be skipped."""
        subscriber = failure.subscriber
        subscriber.email = ""
        subscriber.save()

        send_failure_notification(failure.id)

        mock_send.assert_not_called()
        audit = AuditLog.objects.filter(action="notification_skipped").first()
        assert audit is not None
        assert audit.metadata["reason"] == "no_email"

    @patch("core.tasks.notifications.send_notification_email")
    def test_excluded_subscriber_suppressed(self, mock_send, failure):
        """Excluded subscriber should be suppressed."""
        subscriber = failure.subscriber
        subscriber.excluded_from_automation = True
        subscriber.save()

        send_failure_notification(failure.id)

        mock_send.assert_not_called()
        assert NotificationLog.objects.filter(status="suppressed").count() == 1
        log = NotificationLog.objects.get(status="suppressed")
        assert log.metadata["reason"] == "excluded_from_automation"

    @patch("core.tasks.notifications.send_notification_email")
    def test_opt_out_suppressed(self, mock_send, failure):
        """Opted-out subscriber should be suppressed."""
        NotificationOptOut.objects.create(
            account=failure.account,
            subscriber_email="user@example.com",
        )

        send_failure_notification(failure.id)

        mock_send.assert_not_called()
        assert NotificationLog.objects.filter(status="suppressed").count() == 1
        log = NotificationLog.objects.get(status="suppressed")
        assert log.metadata["reason"] == "opt_out"

    @patch("core.tasks.notifications.send_notification_email")
    def test_duplicate_suppressed(self, mock_send, failure):
        """Duplicate notification for same failure should be suppressed."""
        NotificationLog.objects.create(
            account=failure.account,
            subscriber=failure.subscriber,
            failure=failure,
            email_type="failure_notice",
            status="sent",
            resend_message_id="msg_existing",
        )

        send_failure_notification(failure.id)

        mock_send.assert_not_called()
        assert NotificationLog.objects.filter(status="suppressed").count() == 1

    @patch("core.tasks.notifications.send_notification_email")
    def test_retry_on_api_error(self, mock_send, failure):
        """Should retry on Resend API error."""
        mock_send.side_effect = Exception("API error")

        with pytest.raises(Exception):
            send_failure_notification(failure.id)

    @patch("core.tasks.notifications.send_notification_email")
    def test_dead_letter_on_exhausted_retries(self, mock_send, failure):
        """After max retries, should dead-letter and log failed notification."""
        mock_send.side_effect = Exception("API error")

        # Directly invoke the bound task run method with a mock self
        # to simulate exhausted retries without fighting Celery's request property
        mock_self = MagicMock()
        mock_self.request.retries = 3
        mock_self.max_retries = 3

        # Get the actual function from the task, bypassing Celery's proxy
        task_func = send_failure_notification.run.__func__ if hasattr(send_failure_notification.run, '__func__') else send_failure_notification.run
        task_func(mock_self, failure.id)

        assert DeadLetterLog.objects.count() == 1
        assert NotificationLog.objects.filter(status="failed").count() == 1

        audit = AuditLog.objects.filter(action="notification_failed").first()
        assert audit is not None
        assert audit.outcome == "failed"

    @patch("core.tasks.notifications.send_notification_email")
    def test_nonexistent_failure_handled(self, mock_send):
        """Should handle missing failure gracefully."""
        send_failure_notification(999999)
        mock_send.assert_not_called()
