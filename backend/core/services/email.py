"""
Resend email integration for subscriber notifications.

Builds and sends branded payment failure notification emails.
HTML is inline — no Django template engine (MVP approach per architecture).
"""
import html
import logging
import re

import resend
from django.conf import settings

from core.engine.labels import DECLINE_CODE_LABELS

logger = logging.getLogger(__name__)

# Decline codes that get the "access continues" reassurance
CARD_EXPIRED_CODES = frozenset({"card_expired", "expired_card"})

# Strip CRLF and surrounding control characters from header inputs to prevent
# header injection. Also strips characters that would break the From display name.
_HEADER_INJECTION_CHARS = re.compile(r'[\r\n"<>]')


class EmailConfigurationError(RuntimeError):
    """Raised when email service prerequisites are missing (e.g., no API key)."""


class SkipNotification(RuntimeError):
    """Raised when the notification should be skipped (e.g., no Stripe connection)."""


def _ensure_configured() -> None:
    """Validate Resend configuration just in time. Fails loudly when key is missing."""
    api_key = settings.RESEND_API_KEY
    if not api_key:
        raise EmailConfigurationError("RESEND_API_KEY is not set")
    # Resend SDK reads api_key from module attr on each call.
    resend.api_key = api_key


def _sanitize_header(value: str) -> str:
    """Strip CRLF/quote/angle-bracket characters from values used in email headers."""
    if not value:
        return ""
    return _HEADER_INJECTION_CHARS.sub("", value).strip()


def _build_from_field(company_name: str) -> str:
    """Build the branded From field: '"CompanyName via SafeNet" <notifications@domain>'."""
    domain = settings.SAFENET_SENDING_DOMAIN
    safe_company = _sanitize_header(company_name)
    display_name = f"{safe_company} via SafeNet" if safe_company else "SafeNet"
    return f'"{display_name}" <notifications@{domain}>'


def _build_subject(decline_code: str, company_name: str) -> str:
    """Build subject line — understated for card_expired, standard otherwise."""
    safe_company = _sanitize_header(company_name)
    if decline_code in CARD_EXPIRED_CODES:
        return f"A quick note about your payment — {safe_company}"
    return f"Action needed: update your payment details — {safe_company}"


def _build_html_body(
    company_name: str,
    decline_code: str,
    portal_url: str,
    opt_out_url: str,
) -> str:
    """Build the notification email HTML body."""
    label = DECLINE_CODE_LABELS.get(decline_code, DECLINE_CODE_LABELS["_default"])

    # Escape every interpolated value that originates from account/subscriber
    # data or from a code → label lookup. URLs are NOT escaped because they
    # are placed in href/src attributes and need to remain functional;
    # callers must already have validated/encoded them.
    escaped_company = html.escape(company_name)
    escaped_label = html.escape(label)

    access_note = ""
    if decline_code in CARD_EXPIRED_CODES:
        access_note = (
            '<p style="color:#555;font-size:14px;">'
            "Your access continues while you update your details."
            "</p>"
        )

    return f"""\
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#f9fafb;">
<table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;margin:40px auto;background:#fff;border-radius:8px;border:1px solid #e5e7eb;">
<tr><td style="padding:32px;">
  <h2 style="margin:0 0 16px;color:#111;font-size:20px;">{escaped_company}</h2>
  <p style="color:#333;font-size:16px;line-height:1.5;">Hi,</p>
  <p style="color:#333;font-size:16px;line-height:1.5;">
    We noticed an issue with your recent payment to <strong>{escaped_company}</strong>:
    <strong>{escaped_label}</strong>.
  </p>
  {access_note}
  <p style="color:#333;font-size:16px;line-height:1.5;">
    You can quickly resolve this by updating your payment details:
  </p>
  <table cellpadding="0" cellspacing="0" style="margin:24px 0;">
  <tr><td style="background:#2563eb;border-radius:6px;">
    <a href="{portal_url}" style="display:inline-block;padding:12px 24px;color:#fff;text-decoration:none;font-size:16px;font-weight:600;">
      Update Payment Details
    </a>
  </td></tr>
  </table>
  <p style="color:#999;font-size:12px;line-height:1.4;">
    This email was sent on behalf of {escaped_company} by SafeNet.<br>
    <a href="{opt_out_url}" style="color:#999;">Unsubscribe from payment notifications</a>
  </p>
</td></tr>
</table>
</body>
</html>"""


def send_notification_email(subscriber, failure, account) -> str:
    """
    Send a branded payment failure notification email.

    Args:
        subscriber: Subscriber instance
        failure: SubscriberFailure instance
        account: Account instance (for branding)

    Returns:
        Resend message ID on success.

    Raises:
        EmailConfigurationError if Resend is not configured.
        SkipNotification if account state makes sending impossible (e.g., no
            Stripe connection, no customer-update URL).
        Exception on Resend API failure (caller should retry).
    """
    _ensure_configured()

    company_name = account.company_name or "Your Service"

    # The CTA links to the SaaS owner's own product page. SafeNet does not
    # host the card-update flow.
    customer_update_url = getattr(account, "customer_update_url", "") or ""
    if not customer_update_url:
        raise SkipNotification(
            f"account {account.id} has no customer_update_url configured"
        )

    opt_out_url = "https://app.safenet.app/notifications/opt-out"  # placeholder for Story 4.4

    from_field = _build_from_field(company_name)
    subject = _build_subject(failure.decline_code, company_name)
    html_body = _build_html_body(
        company_name=company_name,
        decline_code=failure.decline_code,
        portal_url=customer_update_url,
        opt_out_url=opt_out_url,
    )

    recipient = (subscriber.email or "").strip().lower()
    if not recipient:
        raise SkipNotification(f"subscriber {subscriber.id} has blank email")

    result = resend.Emails.send({
        "from": from_field,
        "to": [recipient],
        "subject": subject,
        "html": html_body,
    })

    msg_id = result.get("id") if isinstance(result, dict) else getattr(result, "id", None)
    if not msg_id:
        raise RuntimeError(f"Resend returned no message id (response={result!r})")

    logger.info(
        "[send_notification_email] Sent to=%s resend_id=%s failure_id=%s",
        recipient,
        msg_id,
        failure.id,
    )
    return msg_id
