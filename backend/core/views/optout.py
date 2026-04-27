"""Public, unauthenticated, session-less subscriber-facing opt-out endpoint.

Per architecture.md line 921-923 this lives at the project URLConf level
(`/optout/<token>/`), NOT under `/api/v1/`. No DRF, no JWT, no CSRF cookie.

The signed token in the URL IS the proof-of-intent. There is no session to
attack — `@csrf_exempt` is intentional.

Tokens are stateless (Django signing, no DB) and never expire — FR26 / GDPR
transactional contract.

Gate 4 in `tasks/notifications.py` is the suppression source of truth — this
view's only side-effect is creating a `NotificationOptOut` row.
"""
import html
import logging

from django.core.signing import BadSignature
from django.db import transaction
from django.http import HttpResponse
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from core.models.account import Account
from core.models.notification import NotificationOptOut
from core.models.subscriber import Subscriber
from core.services.audit import write_audit_event
from core.services.email import _render_email_shell
from core.services.optout_token import decode_optout_token

logger = logging.getLogger(__name__)


def _html_response(body: str) -> HttpResponse:
    """HTML response with caching disabled — opt-out pages must never be cached
    by intermediate proxies (per-token URLs carry the company name)."""
    response = HttpResponse(body, content_type="text/html", status=200)
    response["Cache-Control"] = "no-store, private"
    return response


def _render_confirm_page(company: str, action_url: str) -> str:
    escaped_company = html.escape(company)
    escaped_action = html.escape(action_url, quote=True)
    inner_html = f"""\
  <p style="color:#333;font-size:16px;line-height:1.5;">
    Confirm: unsubscribe from payment notifications for {escaped_company}.
  </p>
  <form method="POST" action="{escaped_action}">
    <button type="submit" style="display:inline-block;padding:12px 24px;background:#2563eb;color:#fff;border:0;border-radius:6px;font-size:16px;font-weight:600;cursor:pointer;">
      Unsubscribe
    </button>
  </form>"""
    return _render_email_shell(escaped_company, inner_html)


def _render_success_page(company: str) -> str:
    escaped_company = html.escape(company)
    inner_html = f"""\
  <p style="color:#333;font-size:16px;line-height:1.5;">
    You've been unsubscribed from payment notifications for {escaped_company}.
  </p>"""
    return _render_email_shell(escaped_company, inner_html)


def _render_invalid_page() -> str:
    # Visually neutral — passing "" suppresses the brand <h2> in the shell so
    # the page doesn't disclose (or visually slot for) any company identity
    # for an unknown / deleted account.
    inner_html = """\
  <p style="color:#333;font-size:16px;line-height:1.5;">
    This unsubscribe link is no longer valid. If you continue to receive emails, contact the sender directly.
  </p>"""
    return _render_email_shell("", inner_html)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def optout_view(request, token: str):
    # Re-decode on every request — never trust hidden form fields for the
    # email/account_id pair. Catch the broader exception family so a
    # signature-valid-but-shape-wrong payload (future schema drift) routes to
    # the same generic invalid page as a tampered token, instead of 500ing
    # and leaking a status differential.
    try:
        payload = decode_optout_token(token)
        email = payload["email"]
        account_id = payload["account_id"]
        if not isinstance(email, str) or not isinstance(account_id, int):
            raise BadSignature("payload shape mismatch")
    except (BadSignature, KeyError, TypeError, ValueError) as exc:
        # Log exception type only; raw token must NEVER be logged (Sentry leak risk).
        logger.warning(
            "[optout_view] INVALID_TOKEN exception_type=%s",
            type(exc).__name__,
        )
        return _html_response(_render_invalid_page())

    try:
        account = Account.objects.get(pk=account_id)
    except Account.DoesNotExist:
        logger.warning("[optout_view] ACCOUNT_NOT_FOUND account_id=%s", account_id)
        return _html_response(_render_invalid_page())

    company = account.company_name or "this service"

    if request.method == "GET":
        logger.info("[optout_view] GET token_valid=True account_id=%s", account_id)
        action_url = reverse("notification_optout", kwargs={"token": token})
        return _html_response(
            _render_confirm_page(company=company, action_url=action_url)
        )

    # POST — commit the opt-out (idempotent via the unique constraint).
    # Wrap row create + audit write in one savepoint so an audit failure
    # rolls the row back (or vice-versa) — partial-write window closed.
    # `get_or_create` only swallows the unique-violation IntegrityError;
    # FK/NOT NULL/CHECK failures still propagate.
    with transaction.atomic():
        _, created = NotificationOptOut.objects.get_or_create(
            account=account,
            subscriber_email=email,
        )
        if created:
            # Best-effort subscriber lookup for the audit row. May be None —
            # the opt-out works even if SafeNet has no Subscriber row yet
            # (the NotificationOptOut row is the source of truth).
            subscriber = (
                Subscriber.objects
                .for_account(account_id)
                .filter(email__iexact=email)
                .first()
            )
            write_audit_event(
                subscriber=str(subscriber.id) if subscriber else None,
                actor="subscriber",
                action="notification_opted_out",
                outcome="success",
                metadata={
                    "subscriber_email": email,
                    "account_id": account_id,
                    "company_name": account.company_name,
                },
                account=account,
            )

    already_existed = not created
    logger.info(
        "[optout_view] POST opted_out account_id=%s already_existed=%s",
        account_id, already_existed,
    )

    return _html_response(_render_success_page(company=company))
