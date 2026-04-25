"""Tests for the email notification service."""
import pytest
from unittest.mock import patch, MagicMock

from core.services.email import (
    _build_from_field,
    _build_subject,
    _build_html_body,
    send_notification_email,
    CARD_EXPIRED_CODES,
)


class TestBuildFromField:
    def test_includes_company_name(self):
        result = _build_from_field("ProductivityPro")
        assert '"ProductivityPro via SafeNet"' in result
        assert "notifications@" in result

    def test_fallback_when_no_company_name(self):
        result = _build_from_field("")
        assert '"SafeNet"' in result


class TestBuildSubject:
    def test_card_expired_understated(self):
        subject = _build_subject("card_expired", "Acme")
        assert "A quick note" in subject
        assert "Acme" in subject
        assert "Action needed" not in subject

    def test_expired_card_understated(self):
        subject = _build_subject("expired_card", "Acme")
        assert "A quick note" in subject

    def test_other_codes_standard(self):
        subject = _build_subject("insufficient_funds", "Acme")
        assert "Action needed" in subject
        assert "Acme" in subject


class TestBuildHtmlBody:
    def test_contains_company_name(self):
        html = _build_html_body("", "Acme", "insufficient_funds", "https://example.com", "https://optout.com")
        assert "Acme" in html

    def test_contains_failure_explanation(self):
        html = _build_html_body("", "Acme", "insufficient_funds", "https://example.com", "https://optout.com")
        assert "Insufficient funds" in html

    def test_contains_cta_button(self):
        html = _build_html_body("", "Acme", "insufficient_funds", "https://billing.example.com", "https://optout.com")
        assert "https://billing.example.com" in html
        assert "Update Payment Details" in html

    def test_contains_opt_out_link(self):
        html = _build_html_body("", "Acme", "insufficient_funds", "https://example.com", "https://optout.com")
        assert "https://optout.com" in html
        assert "Unsubscribe" in html

    def test_card_expired_access_continues(self):
        html = _build_html_body("", "Acme", "card_expired", "https://example.com", "https://optout.com")
        assert "Your access continues while you update your details" in html

    def test_expired_card_access_continues(self):
        html = _build_html_body("", "Acme", "expired_card", "https://example.com", "https://optout.com")
        assert "Your access continues while you update your details" in html

    def test_non_expired_no_access_note(self):
        html = _build_html_body("", "Acme", "insufficient_funds", "https://example.com", "https://optout.com")
        assert "Your access continues" not in html

    def test_unknown_code_uses_default_label(self):
        html = _build_html_body("", "Acme", "unknown_code_xyz", "https://example.com", "https://optout.com")
        assert "Payment declined" in html


class TestSendNotificationEmail:
    def _make_mocks(self, decline_code="insufficient_funds"):
        subscriber = MagicMock()
        subscriber.email = "subscriber@example.com"
        subscriber.id = 1

        failure = MagicMock()
        failure.decline_code = decline_code
        failure.id = 42

        account = MagicMock()
        account.company_name = "TestCo"
        account.stripe_connection.stripe_user_id = "acct_test123"

        return subscriber, failure, account

    @patch("core.services.email.resend.Emails.send")
    def test_success_returns_message_id(self, mock_send):
        mock_send.return_value = {"id": "msg_abc123"}
        subscriber, failure, account = self._make_mocks()

        msg_id = send_notification_email(subscriber, failure, account)

        assert msg_id == "msg_abc123"
        mock_send.assert_called_once()
        call_args = mock_send.call_args[0][0]
        assert "TestCo via SafeNet" in call_args["from"]
        assert call_args["to"] == ["subscriber@example.com"]

    @patch("core.services.email.resend.Emails.send")
    def test_card_expired_subject(self, mock_send):
        mock_send.return_value = {"id": "msg_abc"}
        subscriber, failure, account = self._make_mocks(decline_code="card_expired")

        send_notification_email(subscriber, failure, account)

        call_args = mock_send.call_args[0][0]
        assert "A quick note" in call_args["subject"]

    @patch("core.services.email.resend.Emails.send")
    def test_raises_on_api_error(self, mock_send):
        mock_send.side_effect = Exception("Resend API error")
        subscriber, failure, account = self._make_mocks()

        with pytest.raises(Exception, match="Resend API error"):
            send_notification_email(subscriber, failure, account)
