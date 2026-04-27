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
from core.models.account import DEFAULT_TONE
from core.services.email_templates import (
    get_final_notice_template,
    get_recovery_confirmation_template,
    get_template,
)
from core.services.optout_token import build_optout_url

logger = logging.getLogger(__name__)

# Decline codes that get the "access continues" reassurance
CARD_EXPIRED_CODES = frozenset({"card_expired", "expired_card"})

# Strip CRLF, Unicode line separators, and characters that break header parsing
# or the From display name. U+2028/U+2029/U+0085 are treated as line breaks by
# some MTAs, so they go through the same filter as \r\n.
_HEADER_INJECTION_CHARS = re.compile(r'[\r\n\u2028\u2029\u0085"<>]')


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


def _build_subject(decline_code: str, company_name: str, tone: str = DEFAULT_TONE) -> str:
    """Build subject line — understated for card_expired, standard otherwise."""
    safe_company = _sanitize_header(company_name)
    template = get_template(tone)
    if decline_code in CARD_EXPIRED_CODES:
        return template.subject_card_expired(safe_company)
    return template.subject_default(safe_company)


def _render_email_shell(escaped_company: str, inner_html: str) -> str:
    """Render the outer email chrome (DOCTYPE → table → brand header → closing tags).

    Single source of truth for all three email types (failure_notice,
    final_notice, recovery_confirmation). The caller passes the *already
    HTML-escaped* company name (used in the visible <h2>) and the
    pre-rendered inner HTML for the body region. When ``escaped_company``
    is empty (e.g. the public opt-out invalid-token page that must not
    disclose any account identity), the brand header is suppressed so the
    page does not render a visibly blank ~36px heading slot.
    """
    header_block = (
        f'  <h2 style="margin:0 0 16px;color:#111;font-size:20px;">{escaped_company}</h2>\n'
        if escaped_company
        else ""
    )
    return f"""\
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"></head>
<body style="margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#f9fafb;">
<table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;margin:40px auto;background:#fff;border-radius:8px;border:1px solid #e5e7eb;">
<tr><td style="padding:32px;">
{header_block}{inner_html}
</td></tr>
</table>
</body>
</html>"""


def _build_html_body(
    company_name: str,
    decline_code: str,
    portal_url: str,
    opt_out_url: str,
    tone: str = DEFAULT_TONE,
) -> str:
    """Build the notification email HTML body."""
    label = DECLINE_CODE_LABELS.get(decline_code, DECLINE_CODE_LABELS["_default"])
    template = get_template(tone)
    is_card_expired = decline_code in CARD_EXPIRED_CODES

    # Templates work with raw values; we escape exactly once at output. Passing
    # pre-escaped values into the templates and re-escaping at output produced
    # visible double-encoding (e.g. "&amp;amp;") in rendered emails.
    escaped_company = html.escape(company_name)
    escaped_portal_url = html.escape(portal_url, quote=True)
    escaped_opt_out_url = html.escape(opt_out_url, quote=True)

    paragraphs_raw = template.body_paragraphs(company_name, label, is_card_expired)
    paragraphs_html = "".join(
        f'<p style="color:#333;font-size:16px;line-height:1.5;">{html.escape(p)}</p>'
        for p in paragraphs_raw
    )

    greeting_html = ""
    if template.greeting:
        greeting_html = (
            f'<p style="color:#333;font-size:16px;line-height:1.5;">'
            f'{html.escape(template.greeting)}</p>'
        )

    cta_label = html.escape(template.cta_label)
    footer_text = html.escape(template.footer(company_name))

    inner_html = f"""\
  {greeting_html}
  {paragraphs_html}
  <table cellpadding="0" cellspacing="0" style="margin:24px 0;">
  <tr><td style="background:#2563eb;border-radius:6px;">
    <a href="{escaped_portal_url}" style="display:inline-block;padding:12px 24px;color:#fff;text-decoration:none;font-size:16px;font-weight:600;">
      {cta_label}
    </a>
  </td></tr>
  </table>
  <p style="color:#999;font-size:12px;line-height:1.4;">
    {footer_text}<br>
    <a href="{escaped_opt_out_url}" style="color:#999;">Unsubscribe from payment notifications</a>
  </p>"""

    return _render_email_shell(escaped_company, inner_html)


def _build_final_notice_subject(company_name: str, tone: str = DEFAULT_TONE) -> str:
    """Build subject line for the final notice email (decline-code-agnostic)."""
    safe_company = _sanitize_header(company_name)
    template = get_final_notice_template(tone)
    return _sanitize_header(template.subject(safe_company))


def _build_final_notice_html_body(
    company_name: str,
    portal_url: str,
    opt_out_url: str,
    tone: str = DEFAULT_TONE,
) -> str:
    """Build the final-notice email HTML body (carries a CTA, decline-code-agnostic)."""
    template = get_final_notice_template(tone)

    escaped_company = html.escape(company_name)
    escaped_portal_url = html.escape(portal_url, quote=True)
    escaped_opt_out_url = html.escape(opt_out_url, quote=True)

    paragraphs_raw = template.body_paragraphs(company_name)
    paragraphs_html = "".join(
        f'<p style="color:#333;font-size:16px;line-height:1.5;">{html.escape(p)}</p>'
        for p in paragraphs_raw
    )

    greeting_html = ""
    if template.greeting:
        greeting_html = (
            f'<p style="color:#333;font-size:16px;line-height:1.5;">'
            f'{html.escape(template.greeting)}</p>'
        )

    cta_label = html.escape(template.cta_label)
    footer_text = html.escape(template.footer(company_name))

    inner_html = f"""\
  {greeting_html}
  {paragraphs_html}
  <table cellpadding="0" cellspacing="0" style="margin:24px 0;">
  <tr><td style="background:#2563eb;border-radius:6px;">
    <a href="{escaped_portal_url}" style="display:inline-block;padding:12px 24px;color:#fff;text-decoration:none;font-size:16px;font-weight:600;">
      {cta_label}
    </a>
  </td></tr>
  </table>
  <p style="color:#999;font-size:12px;line-height:1.4;">
    {footer_text}<br>
    <a href="{escaped_opt_out_url}" style="color:#999;">Unsubscribe from payment notifications</a>
  </p>"""

    return _render_email_shell(escaped_company, inner_html)


def _build_recovery_confirmation_subject(company_name: str, tone: str = DEFAULT_TONE) -> str:
    """Build subject line for the recovery confirmation email."""
    safe_company = _sanitize_header(company_name)
    template = get_recovery_confirmation_template(tone)
    return _sanitize_header(template.subject(safe_company))


def _build_recovery_confirmation_html_body(
    company_name: str,
    opt_out_url: str,
    tone: str = DEFAULT_TONE,
) -> str:
    """Build the recovery-confirmation email HTML body (no CTA — just acknowledgement)."""
    template = get_recovery_confirmation_template(tone)

    escaped_company = html.escape(company_name)
    escaped_opt_out_url = html.escape(opt_out_url, quote=True)

    paragraphs_raw = template.body_paragraphs(company_name)
    paragraphs_html = "".join(
        f'<p style="color:#333;font-size:16px;line-height:1.5;">{html.escape(p)}</p>'
        for p in paragraphs_raw
    )

    greeting_html = ""
    if template.greeting:
        greeting_html = (
            f'<p style="color:#333;font-size:16px;line-height:1.5;">'
            f'{html.escape(template.greeting)}</p>'
        )

    footer_text = html.escape(template.footer(company_name))

    inner_html = f"""\
  {greeting_html}
  {paragraphs_html}
  <p style="color:#999;font-size:12px;line-height:1.4;">
    {footer_text}<br>
    <a href="{escaped_opt_out_url}" style="color:#999;">Unsubscribe from payment notifications</a>
  </p>"""

    return _render_email_shell(escaped_company, inner_html)


def _build_password_reset_subject() -> str:
    """Subject for the SafeNet password reset email — literal, no per-account variation."""
    return "Reset your SafeNet password"


def _build_password_reset_html_body(reset_url: str) -> str:
    """SafeNet-branded password reset email body. Reuses `_render_email_shell`
    with the literal company name "SafeNet" so the brand <h2> reads correctly.

    This is a SafeNet-to-founder email — NOT a per-tenant branded subscriber
    email — so it does NOT use `_build_from_field`.
    """
    if not reset_url:
        raise ValueError("reset_url must be a non-empty string")
    escaped_url = html.escape(reset_url, quote=True)
    inner_html = f"""\
  <p style="color:#333;font-size:16px;line-height:1.5;">Hi,</p>
  <p style="color:#333;font-size:16px;line-height:1.5;">
    We received a request to reset the password for your SafeNet account.
    Click the button below to choose a new password. This link expires in 1 hour.
  </p>
  <table cellpadding="0" cellspacing="0" style="margin:24px 0;">
  <tr><td style="background:#2563eb;border-radius:6px;">
    <a href="{escaped_url}" style="display:inline-block;padding:12px 24px;color:#fff;text-decoration:none;font-size:16px;font-weight:600;">
      Reset password
    </a>
  </td></tr>
  </table>
  <p style="color:#999;font-size:12px;line-height:1.4;">
    If you didn't request a password reset, you can safely ignore this email — your password will not change.
  </p>"""
    return _render_email_shell("SafeNet", inner_html)


def _build_password_changed_subject() -> str:
    return "Your SafeNet password was changed"


def _build_password_changed_html_body() -> str:
    """SafeNet-branded notification sent after a successful password reset."""
    inner_html = """\
  <p style="color:#333;font-size:16px;line-height:1.5;">Hi,</p>
  <p style="color:#333;font-size:16px;line-height:1.5;">
    Your SafeNet password was just changed. If this was you, no further action is needed.
  </p>
  <p style="color:#333;font-size:16px;line-height:1.5;">
    If this wasn't you, contact support immediately.
  </p>"""
    return _render_email_shell("SafeNet", inner_html)


def send_password_changed_notification_email(user) -> str:
    """Send a notification email confirming the password was just changed.

    Best-effort: caller is expected to write a `DeadLetterLog` row on failure
    and still return success to the client (the password change itself
    has already been committed and must not be undone).
    """
    _ensure_configured()
    domain = settings.SAFENET_SENDING_DOMAIN
    from_field = f'"SafeNet" <noreply@{domain}>'
    recipient = (user.email or "").strip().lower()
    if not recipient:
        raise SkipNotification(f"user {user.id} has no email")

    subject = _build_password_changed_subject()
    html_body = _build_password_changed_html_body()

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
        "[send_password_changed_notification_email] Sent to=%s resend_id=%s user_id=%s",
        recipient, msg_id, user.id,
    )
    return msg_id


def send_password_reset_email(user, reset_url: str) -> str:
    """Send a SafeNet-branded password reset email to a registered user.

    Uses Resend (configured by `_ensure_configured`). Raises any Resend
    exception to the caller — the view layer is responsible for the
    constant-response contract (always return 200 generic to the client
    even if Resend fails).
    """
    _ensure_configured()
    domain = settings.SAFENET_SENDING_DOMAIN
    from_field = f'"SafeNet" <noreply@{domain}>'
    recipient = (user.email or "").strip().lower()
    if not recipient:
        raise SkipNotification(f"user {user.id} has no email")

    subject = _build_password_reset_subject()
    html_body = _build_password_reset_html_body(reset_url)

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
        "[send_password_reset_email] Sent to=%s resend_id=%s user_id=%s",
        recipient, msg_id, user.id,
    )
    return msg_id


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
    tone = account.notification_tone or DEFAULT_TONE

    # The CTA links to the SaaS owner's own product page. SafeNet does not
    # host the card-update flow.
    customer_update_url = (getattr(account, "customer_update_url", "") or "").strip()
    if not customer_update_url:
        raise SkipNotification(
            f"account {account.id} has no customer_update_url configured"
        )

    opt_out_url = build_optout_url(
        subscriber_email=(subscriber.email or "").strip().lower(),
        account_id=account.id,
    )

    from_field = _build_from_field(company_name)
    subject = _build_subject(failure.decline_code, company_name, tone)
    html_body = _build_html_body(
        company_name=company_name,
        decline_code=failure.decline_code,
        portal_url=customer_update_url,
        opt_out_url=opt_out_url,
        tone=tone,
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


def send_final_notice_email(subscriber, failure, account) -> str:
    """
    Send a final notice email — the "last attempt" warning before passive churn.

    Carries a CTA to the SaaS owner's customer-update URL. Same configuration
    contract as send_notification_email: raises SkipNotification when the URL
    is not configured (parity — final notice has a CTA).

    Returns:
        Resend message ID on success.
    """
    _ensure_configured()

    company_name = account.company_name or "Your Service"
    tone = account.notification_tone or DEFAULT_TONE

    customer_update_url = (getattr(account, "customer_update_url", "") or "").strip()
    if not customer_update_url:
        raise SkipNotification(
            f"account {account.id} has no customer_update_url configured"
        )

    opt_out_url = build_optout_url(
        subscriber_email=(subscriber.email or "").strip().lower(),
        account_id=account.id,
    )

    from_field = _build_from_field(company_name)
    subject = _build_final_notice_subject(company_name, tone)
    html_body = _build_final_notice_html_body(
        company_name=company_name,
        portal_url=customer_update_url,
        opt_out_url=opt_out_url,
        tone=tone,
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
        "[send_final_notice_email] Sent to=%s resend_id=%s failure_id=%s",
        recipient,
        msg_id,
        failure.id,
    )
    return msg_id


def send_recovery_confirmation_email(subscriber, failure, account) -> str:
    """
    Send a recovery confirmation email — short acknowledgement after a successful retry.

    No CTA: the recovery has already happened, so the email is exempt from the
    customer_update_url SkipNotification guard. Per UX line 771, body is
    capped at two paragraphs (enforced by the template construction).

    Returns:
        Resend message ID on success.
    """
    _ensure_configured()

    company_name = account.company_name or "Your Service"
    tone = account.notification_tone or DEFAULT_TONE

    opt_out_url = build_optout_url(
        subscriber_email=(subscriber.email or "").strip().lower(),
        account_id=account.id,
    )

    from_field = _build_from_field(company_name)
    subject = _build_recovery_confirmation_subject(company_name, tone)
    html_body = _build_recovery_confirmation_html_body(
        company_name=company_name,
        opt_out_url=opt_out_url,
        tone=tone,
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
        "[send_recovery_confirmation_email] Sent to=%s resend_id=%s failure_id=%s",
        recipient,
        msg_id,
        failure.id,
    )
    return msg_id
