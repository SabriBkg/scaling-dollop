"""
Resend email integration for subscriber notifications.

Builds and sends branded payment failure notification emails.
HTML is inline — no Django template engine (MVP approach per architecture).
"""
import logging

import resend
from django.conf import settings

from core.engine.labels import DECLINE_CODE_LABELS

logger = logging.getLogger(__name__)

resend.api_key = settings.RESEND_API_KEY

# Decline codes that get the "access continues" reassurance
CARD_EXPIRED_CODES = frozenset({"card_expired", "expired_card"})


def _build_from_field(company_name: str) -> str:
    """Build the branded From field: '"CompanyName via SafeNet" <notifications@domain>'."""
    domain = settings.SAFENET_SENDING_DOMAIN
    display_name = f"{company_name} via SafeNet" if company_name else "SafeNet"
    return f'"{display_name}" <notifications@{domain}>'


def _build_subject(decline_code: str, company_name: str) -> str:
    """Build subject line — understated for card_expired, standard otherwise."""
    if decline_code in CARD_EXPIRED_CODES:
        return f"A quick note about your payment — {company_name}"
    return f"Action needed: update your payment details — {company_name}"


def _build_html_body(
    subscriber_name: str,
    company_name: str,
    decline_code: str,
    portal_url: str,
    opt_out_url: str,
) -> str:
    """Build the notification email HTML body."""
    label = DECLINE_CODE_LABELS.get(decline_code, DECLINE_CODE_LABELS["_default"])

    access_note = ""
    if decline_code in CARD_EXPIRED_CODES:
        access_note = (
            '<p style="color:#555;font-size:14px;">'
            "Your access continues while you update your details."
            "</p>"
        )

    greeting = f"Hi{' ' + subscriber_name if subscriber_name else ''},"

    return f"""\
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#f9fafb;">
<table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;margin:40px auto;background:#fff;border-radius:8px;border:1px solid #e5e7eb;">
<tr><td style="padding:32px;">
  <h2 style="margin:0 0 16px;color:#111;font-size:20px;">{company_name}</h2>
  <p style="color:#333;font-size:16px;line-height:1.5;">{greeting}</p>
  <p style="color:#333;font-size:16px;line-height:1.5;">
    We noticed an issue with your recent payment to <strong>{company_name}</strong>:
    <strong>{label}</strong>.
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
    This email was sent on behalf of {company_name} by SafeNet.<br>
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
        Exception on Resend API failure.
    """
    company_name = account.company_name or "Your Service"
    stripe_user_id = account.stripe_connection.stripe_user_id
    portal_url = f"https://billing.stripe.com/p/login/{stripe_user_id}"
    opt_out_url = f"https://app.safenet.app/notifications/opt-out"  # placeholder for Story 4.4

    subscriber_name = ""
    if hasattr(subscriber, "email") and subscriber.email:
        # Use the part before @ as a rough name if no name field exists
        subscriber_name = ""

    from_field = _build_from_field(company_name)
    subject = _build_subject(failure.decline_code, company_name)
    html_body = _build_html_body(
        subscriber_name=subscriber_name,
        company_name=company_name,
        decline_code=failure.decline_code,
        portal_url=portal_url,
        opt_out_url=opt_out_url,
    )

    result = resend.Emails.send({
        "from": from_field,
        "to": [subscriber.email],
        "subject": subject,
        "html": html_body,
    })

    msg_id = result.get("id") if isinstance(result, dict) else getattr(result, "id", str(result))
    logger.info(
        "[send_notification_email] Sent to=%s resend_id=%s failure_id=%s",
        subscriber.email,
        msg_id,
        failure.id,
    )
    return msg_id
