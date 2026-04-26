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


@pytest.fixture(autouse=True)
def _resend_configured(settings):
    """Provide a non-empty Resend API key so _ensure_configured passes."""
    settings.RESEND_API_KEY = "test_key"
    settings.SAFENET_SENDING_DOMAIN = "payments.safenet.app"


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
        html = _build_html_body("Acme", "insufficient_funds", "https://example.com", "https://optout.com")
        assert "Acme" in html

    def test_contains_failure_explanation(self):
        html = _build_html_body("Acme", "insufficient_funds", "https://example.com", "https://optout.com")
        assert "Insufficient funds" in html

    def test_contains_cta_button(self):
        html = _build_html_body("Acme", "insufficient_funds", "https://billing.example.com", "https://optout.com")
        assert "https://billing.example.com" in html
        assert "Update Payment Details" in html

    def test_contains_opt_out_link(self):
        html = _build_html_body("Acme", "insufficient_funds", "https://example.com", "https://optout.com")
        assert "https://optout.com" in html
        assert "Unsubscribe" in html

    def test_card_expired_access_continues(self):
        html = _build_html_body("Acme", "card_expired", "https://example.com", "https://optout.com")
        assert "Your access continues while you update your details" in html

    def test_expired_card_access_continues(self):
        html = _build_html_body("Acme", "expired_card", "https://example.com", "https://optout.com")
        assert "Your access continues while you update your details" in html

    def test_non_expired_no_access_note(self):
        html = _build_html_body("Acme", "insufficient_funds", "https://example.com", "https://optout.com")
        assert "Your access continues" not in html

    def test_unknown_code_uses_default_label(self):
        html = _build_html_body("Acme", "unknown_code_xyz", "https://example.com", "https://optout.com")
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
        account.customer_update_url = "https://example.com/update"
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


class TestToneAwareSubjects:
    """Subjects must vary by tone — single source of truth in email_templates.py."""

    def test_friendly_default_subject(self):
        subject = _build_subject("insufficient_funds", "Acme", tone="friendly")
        assert "heads-up" in subject.lower()
        assert "Acme" in subject

    def test_friendly_card_expired_subject(self):
        subject = _build_subject("card_expired", "Acme", tone="friendly")
        assert "refresh" in subject.lower() or "hey" in subject.lower()

    def test_minimal_default_subject(self):
        subject = _build_subject("insufficient_funds", "Acme", tone="minimal")
        assert subject == "Payment failed — Acme"

    def test_minimal_card_expired_subject(self):
        subject = _build_subject("card_expired", "Acme", tone="minimal")
        assert subject == "Card expired — Acme"

    def test_unknown_tone_falls_back_to_default(self):
        # Unknown tone string falls back to professional default.
        subject = _build_subject("insufficient_funds", "Acme", tone="shouting")
        assert "Action needed" in subject


class TestToneAwareBody:
    def test_friendly_body_uses_contractions(self):
        html_body = _build_html_body(
            "Acme", "insufficient_funds",
            "https://example.com", "https://optout.com",
            tone="friendly",
        )
        # Friendly voice: "couldn't process". Body paragraphs are HTML-escaped
        # at output, so the apostrophe renders as &#x27; — but accept either
        # form to keep the test robust against escape-policy tweaks.
        assert "couldn&#x27;t" in html_body or "couldn't" in html_body

    def test_minimal_body_has_max_two_paragraphs(self):
        """Body section must contain ≤2 inner <p> blocks (excluding footer)."""
        import re

        html_body = _build_html_body(
            "Acme", "insufficient_funds",
            "https://example.com", "https://optout.com",
            tone="minimal",
        )
        # Count <p> blocks that carry the body styling (color:#333). The footer
        # uses color:#999 and is excluded by this filter.
        body_paragraph_count = len(re.findall(r'<p style="color:#333', html_body))
        assert body_paragraph_count <= 2, (
            f"Minimal tone produced {body_paragraph_count} body paragraphs; cap is 2"
        )

    def test_minimal_body_has_max_two_paragraphs_card_expired(self):
        import re

        html_body = _build_html_body(
            "Acme", "card_expired",
            "https://example.com", "https://optout.com",
            tone="minimal",
        )
        body_paragraph_count = len(re.findall(r'<p style="color:#333', html_body))
        assert body_paragraph_count <= 2

    def test_minimal_has_no_greeting(self):
        html_body = _build_html_body(
            "Acme", "insufficient_funds",
            "https://example.com", "https://optout.com",
            tone="minimal",
        )
        assert "Hello," not in html_body
        assert "Hi there" not in html_body

    def test_card_expired_reassurance_present_in_all_tones(self):
        """AC 3: access-continues reassurance must appear in every tone for card_expired."""
        for tone in ("professional", "friendly", "minimal"):
            html_body = _build_html_body(
                "Acme", "card_expired",
                "https://example.com", "https://optout.com",
                tone=tone,
            )
            # Each tone phrases it differently; the unifying word is "access".
            assert "access" in html_body.lower(), f"tone={tone} missing reassurance"


class TestToneAwareEscaping:
    """4-1 escape guarantees must hold across every tone (no XSS regression)."""

    @pytest.mark.parametrize("tone", ["professional", "friendly", "minimal"])
    def test_company_name_html_escaped(self, tone):
        html_body = _build_html_body(
            '<script>alert(1)</script>', "insufficient_funds",
            "https://example.com", "https://optout.com",
            tone=tone,
        )
        assert "<script>alert(1)</script>" not in html_body
        assert "&lt;script&gt;" in html_body

    @pytest.mark.parametrize("tone", ["professional", "friendly", "minimal"])
    def test_subject_strips_crlf_in_company(self, tone):
        subject = _build_subject(
            "insufficient_funds",
            "Acme\r\nBcc: attacker@evil.com",
            tone=tone,
        )
        assert "\r" not in subject
        assert "\n" not in subject

    @pytest.mark.parametrize("tone", ["professional", "friendly", "minimal"])
    def test_company_name_escaped_consistently_in_footer(self, tone):
        """Footer must single-escape the company name, not double-escape.

        Regression guard for a bug where the footer was html.escape()-ed twice,
        producing visible '&amp;amp;' / '&amp;lt;' fragments in rendered emails
        for company names containing HTML metachars.
        """
        html_body = _build_html_body(
            "Tom & Jerry, Inc.", "insufficient_funds",
            "https://example.com", "https://optout.com",
            tone=tone,
        )
        # Single-escape: "&amp;" present.
        assert "Tom &amp; Jerry, Inc." in html_body
        # Double-escape: "&amp;amp;" must NOT appear anywhere in the body.
        assert "&amp;amp;" not in html_body

    @pytest.mark.parametrize("tone", ["professional", "friendly", "minimal"])
    def test_portal_url_escaped_in_href(self, tone):
        """CTA href must escape attribute-breaking characters in portal_url."""
        html_body = _build_html_body(
            "Acme", "insufficient_funds",
            'https://example.com/?x="><script>alert(1)</script>',
            "https://optout.com",
            tone=tone,
        )
        assert '"><script>' not in html_body
        assert "&quot;&gt;&lt;script&gt;" in html_body


class TestSendNotificationEmailRoundTrip:
    """The email sent and the preview must render from identical helpers."""

    @patch("core.services.email.resend.Emails.send")
    def test_friendly_tone_round_trip_matches_helper(self, mock_send, settings):
        settings.RESEND_API_KEY = "test_key"
        settings.SAFENET_SENDING_DOMAIN = "payments.safenet.app"
        mock_send.return_value = {"id": "msg_rt"}

        subscriber = MagicMock()
        subscriber.email = "subscriber@example.com"
        subscriber.id = 1

        failure = MagicMock()
        failure.decline_code = "card_expired"
        failure.id = 99

        account = MagicMock()
        account.company_name = "RoundTripCo"
        account.customer_update_url = "https://example.com/update"
        account.notification_tone = "friendly"

        send_notification_email(subscriber, failure, account)

        sent_html = mock_send.call_args[0][0]["html"]
        expected_html = _build_html_body(
            company_name="RoundTripCo",
            decline_code="card_expired",
            portal_url="https://example.com/update",
            opt_out_url="https://app.safenet.app/notifications/opt-out",
            tone="friendly",
        )
        assert sent_html == expected_html

        sent_subject = mock_send.call_args[0][0]["subject"]
        expected_subject = _build_subject("card_expired", "RoundTripCo", tone="friendly")
        assert sent_subject == expected_subject

    @patch("core.services.email.resend.Emails.send")
    def test_missing_tone_defaults_to_professional(self, mock_send, settings):
        settings.RESEND_API_KEY = "test_key"
        settings.SAFENET_SENDING_DOMAIN = "payments.safenet.app"
        mock_send.return_value = {"id": "msg_rt2"}

        subscriber = MagicMock()
        subscriber.email = "subscriber@example.com"
        subscriber.id = 1

        failure = MagicMock()
        failure.decline_code = "insufficient_funds"
        failure.id = 100

        account = MagicMock()
        account.company_name = "DefaultCo"
        account.customer_update_url = "https://example.com/update"
        account.notification_tone = None  # legacy account, no tone saved

        send_notification_email(subscriber, failure, account)

        sent_subject = mock_send.call_args[0][0]["subject"]
        # Professional default subject
        assert "Action needed" in sent_subject
