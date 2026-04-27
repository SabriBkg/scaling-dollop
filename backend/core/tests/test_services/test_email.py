"""Tests for the email notification service."""
import pytest
from unittest.mock import patch, MagicMock

from core.services.email import (
    SkipNotification,
    _build_final_notice_html_body,
    _build_final_notice_subject,
    _build_from_field,
    _build_html_body,
    _build_password_reset_html_body,
    _build_recovery_confirmation_html_body,
    _build_recovery_confirmation_subject,
    _build_subject,
    send_final_notice_email,
    send_notification_email,
    send_recovery_confirmation_email,
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
        account.id = 1
        account.company_name = "RoundTripCo"
        account.customer_update_url = "https://example.com/update"
        account.notification_tone = "friendly"

        send_notification_email(subscriber, failure, account)

        sent_html = mock_send.call_args[0][0]["html"]
        # The opt-out URL now contains a signed token (Story 4.4). Assert the
        # email shape rather than a literal URL: it must use the subscriber's
        # canonicalized email + the account id.
        from core.services.optout_token import build_optout_url
        expected_html = _build_html_body(
            company_name="RoundTripCo",
            decline_code="card_expired",
            portal_url="https://example.com/update",
            opt_out_url=build_optout_url(
                subscriber_email="subscriber@example.com",
                account_id=1,
            ),
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


# ---------------------------------------------------------------------------
# Story 4.3 — final notice & recovery confirmation
# ---------------------------------------------------------------------------


class TestFinalNoticeSubject:
    @pytest.mark.parametrize("tone,expected_phrase", [
        ("professional", "Final attempt"),
        ("friendly", "last try"),
        ("minimal", "Final attempt"),
    ])
    def test_final_notice_subject_uses_tone(self, tone, expected_phrase):
        subject = _build_final_notice_subject("Acme", tone=tone)
        assert expected_phrase in subject
        assert "Acme" in subject

    def test_final_notice_subject_strips_crlf(self):
        subject = _build_final_notice_subject("Acme\r\nBcc: attacker@evil.com", tone="professional")
        assert "\r" not in subject
        assert "\n" not in subject

    def test_final_notice_unknown_tone_falls_back(self):
        subject = _build_final_notice_subject("Acme", tone="shouting")
        assert "Final attempt" in subject

    def test_final_notice_empty_tone_falls_back(self):
        subject = _build_final_notice_subject("Acme", tone="")
        assert "Final attempt" in subject


class TestFinalNoticeBody:
    @pytest.mark.parametrize("tone", ["professional", "friendly", "minimal"])
    def test_final_notice_body_contains_canonical_message(self, tone):
        """Every tone's body must voice the substance of "last attempt → paused"."""
        html = _build_final_notice_html_body(
            "Acme", "https://example.com/update", "https://optout.com",
            tone=tone,
        )
        lower = html.lower()
        assert "last attempt" in lower or "final attempt" in lower or "last try" in lower
        assert "paused" in lower

    @pytest.mark.parametrize("tone", ["professional", "friendly", "minimal"])
    def test_final_notice_html_escapes_company_name(self, tone):
        html = _build_final_notice_html_body(
            "<script>alert(1)</script>", "https://example.com/update", "https://optout.com",
            tone=tone,
        )
        assert "<script>alert(1)</script>" not in html
        assert "&lt;script&gt;" in html

    @pytest.mark.parametrize("tone", ["professional", "friendly", "minimal"])
    def test_final_notice_footer_single_escapes_company(self, tone):
        """Footer must single-escape company name (no &amp;amp; double-encoding)."""
        html = _build_final_notice_html_body(
            "Tom & Jerry, Inc.", "https://example.com/update", "https://optout.com",
            tone=tone,
        )
        assert "Tom &amp; Jerry, Inc." in html
        assert "&amp;amp;" not in html

    @pytest.mark.parametrize("tone", ["professional", "friendly", "minimal"])
    def test_final_notice_contains_cta_and_opt_out(self, tone):
        html = _build_final_notice_html_body(
            "Acme", "https://billing.example.com", "https://optout.com",
            tone=tone,
        )
        assert "https://billing.example.com" in html
        assert "https://optout.com" in html

    def test_final_notice_minimal_has_no_greeting(self):
        html = _build_final_notice_html_body(
            "Acme", "https://example.com/update", "https://optout.com",
            tone="minimal",
        )
        assert "Hello," not in html
        assert "Hi there" not in html


class TestSendFinalNoticeEmail:
    def _make_mocks(self, customer_update_url="https://example.com/update"):
        subscriber = MagicMock()
        subscriber.email = "subscriber@example.com"
        subscriber.id = 1

        failure = MagicMock()
        failure.id = 42

        account = MagicMock()
        account.company_name = "TestCo"
        account.customer_update_url = customer_update_url
        account.notification_tone = "professional"
        return subscriber, failure, account

    @patch("core.services.email.resend.Emails.send")
    def test_success_returns_message_id(self, mock_send):
        mock_send.return_value = {"id": "msg_fn_1"}
        subscriber, failure, account = self._make_mocks()

        msg_id = send_final_notice_email(subscriber, failure, account)

        assert msg_id == "msg_fn_1"
        call_args = mock_send.call_args[0][0]
        assert "TestCo via SafeNet" in call_args["from"]
        assert call_args["to"] == ["subscriber@example.com"]
        assert "Final attempt" in call_args["subject"]

    @patch("core.services.email.resend.Emails.send")
    def test_skip_when_no_customer_update_url(self, mock_send):
        subscriber, failure, account = self._make_mocks(customer_update_url="")

        with pytest.raises(SkipNotification):
            send_final_notice_email(subscriber, failure, account)
        mock_send.assert_not_called()

    @patch("core.services.email.resend.Emails.send")
    def test_skip_when_blank_email(self, mock_send):
        subscriber, failure, account = self._make_mocks()
        subscriber.email = ""

        with pytest.raises(SkipNotification):
            send_final_notice_email(subscriber, failure, account)
        mock_send.assert_not_called()


class TestRecoveryConfirmationSubject:
    @pytest.mark.parametrize("tone,expected_phrase", [
        ("professional", "Payment confirmed"),
        ("friendly", "All sorted"),
        ("minimal", "Payment confirmed"),
    ])
    def test_recovery_confirmation_subject_uses_tone(self, tone, expected_phrase):
        subject = _build_recovery_confirmation_subject("Acme", tone=tone)
        assert expected_phrase in subject
        assert "Acme" in subject

    def test_recovery_confirmation_subject_strips_crlf(self):
        subject = _build_recovery_confirmation_subject(
            "Acme\r\nBcc: attacker@evil.com", tone="professional",
        )
        assert "\r" not in subject
        assert "\n" not in subject


class TestRecoveryConfirmationBody:
    @pytest.mark.parametrize("tone", ["professional", "friendly", "minimal"])
    def test_recovery_confirmation_body_max_two_paragraphs(self, tone):
        """UX line 771: brief — two paragraphs maximum across every tone.

        Cap is enforced by construction: `body_paragraphs` returns a fixed-length
        list literal per tone. We assert against the template directly because
        the greeting renders with the same `color:#333` style, so an HTML-only
        regex would conflate body and greeting.
        """
        from core.services.email_templates import get_recovery_confirmation_template

        template = get_recovery_confirmation_template(tone)
        paragraphs = template.body_paragraphs("Acme")
        assert len(paragraphs) <= 2, (
            f"tone={tone} produced {len(paragraphs)} body paragraphs; cap is 2"
        )

    @pytest.mark.parametrize("tone", ["professional", "friendly", "minimal"])
    def test_recovery_confirmation_no_cta_button(self, tone):
        """The recovery confirmation must NOT contain the CTA button styling/href."""
        html = _build_recovery_confirmation_html_body(
            "Acme", "https://optout.com", tone=tone,
        )
        # CTA button color from _build_html_body:116 — must not appear here
        assert "background:#2563eb" not in html
        # Only one <a> link should exist (the opt-out)
        import re
        anchors = re.findall(r"<a\s+href=", html)
        assert len(anchors) == 1

    @pytest.mark.parametrize("tone", ["professional", "friendly", "minimal"])
    def test_recovery_confirmation_html_escapes_company_name(self, tone):
        html = _build_recovery_confirmation_html_body(
            "<script>alert(1)</script>", "https://optout.com", tone=tone,
        )
        assert "<script>alert(1)</script>" not in html
        assert "&lt;script&gt;" in html

    @pytest.mark.parametrize("tone", ["professional", "friendly", "minimal"])
    def test_recovery_confirmation_footer_single_escapes_company(self, tone):
        html = _build_recovery_confirmation_html_body(
            "Tom & Jerry, Inc.", "https://optout.com", tone=tone,
        )
        assert "Tom &amp; Jerry, Inc." in html
        assert "&amp;amp;" not in html

    def test_recovery_confirmation_minimal_has_one_paragraph(self):
        import re
        html = _build_recovery_confirmation_html_body(
            "Acme", "https://optout.com", tone="minimal",
        )
        body_paragraph_count = len(re.findall(r'<p style="color:#333', html))
        assert body_paragraph_count == 1


class TestSendRecoveryConfirmationEmail:
    def _make_mocks(self, customer_update_url="https://example.com/update"):
        subscriber = MagicMock()
        subscriber.email = "subscriber@example.com"
        subscriber.id = 1

        failure = MagicMock()
        failure.id = 99

        account = MagicMock()
        account.company_name = "TestCo"
        account.customer_update_url = customer_update_url
        account.notification_tone = "professional"
        return subscriber, failure, account

    @patch("core.services.email.resend.Emails.send")
    def test_success_returns_message_id(self, mock_send):
        mock_send.return_value = {"id": "msg_rc_1"}
        subscriber, failure, account = self._make_mocks()

        msg_id = send_recovery_confirmation_email(subscriber, failure, account)

        assert msg_id == "msg_rc_1"
        call_args = mock_send.call_args[0][0]
        assert "TestCo via SafeNet" in call_args["from"]
        assert call_args["to"] == ["subscriber@example.com"]
        assert "Payment confirmed" in call_args["subject"]

    @patch("core.services.email.resend.Emails.send")
    def test_sends_without_customer_update_url(self, mock_send):
        """Recovery confirmation has no CTA — customer_update_url is irrelevant."""
        mock_send.return_value = {"id": "msg_rc_2"}
        subscriber, failure, account = self._make_mocks(customer_update_url="")

        msg_id = send_recovery_confirmation_email(subscriber, failure, account)

        assert msg_id == "msg_rc_2"

    @patch("core.services.email.resend.Emails.send")
    def test_skip_when_blank_email(self, mock_send):
        subscriber, failure, account = self._make_mocks()
        subscriber.email = ""

        with pytest.raises(SkipNotification):
            send_recovery_confirmation_email(subscriber, failure, account)
        mock_send.assert_not_called()


class TestPasswordResetEmailBody:
    """Story 4.5 — password reset email rendering guards."""

    def test_renders_non_empty_href(self):
        html_body = _build_password_reset_html_body("https://app.safenet.test/reset-password/u/t")
        # Defense check: the CTA href must NOT be empty (would open the user's
        # own inbox on click).
        assert 'href=""' not in html_body
        assert 'href="https://app.safenet.test/reset-password/u/t"' in html_body

    def test_rejects_empty_reset_url(self):
        with pytest.raises(ValueError):
            _build_password_reset_html_body("")

    def test_contains_greeting_paragraph(self):
        html_body = _build_password_reset_html_body("https://app.safenet.test/reset-password/u/t")
        # AC 6: greeting paragraph must precede the explanatory paragraph.
        assert ">Hi,<" in html_body


class TestEmailShellInvariant:
    """Refactor guard: extracting `_render_email_shell` must not change failure-notice rendering."""

    def test_shell_extraction_preserves_outer_chrome(self):
        """The DOCTYPE / table chrome must still appear exactly once in the failure-notice render."""
        html_body = _build_html_body(
            "Acme", "insufficient_funds",
            "https://example.com", "https://optout.com",
            tone="professional",
        )
        # Outer chrome contracts.
        assert html_body.startswith("<!DOCTYPE html>\n<html>")
        assert html_body.endswith("</html>")
        # Body table styling — single-source-of-truth check on the shell.
        assert 'max-width:600px' in html_body
        assert html_body.count('<!DOCTYPE html>') == 1
