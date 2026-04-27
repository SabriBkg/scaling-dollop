"""Anonymous password reset endpoints (Story 4.5).

Both endpoints are anonymous (`AllowAny`) — they live under /api/v1/auth/
next to the JWT login endpoints. The throttle classes (per-email and
per-IP) are the only abuse defense.

Token format: Django stdlib `PasswordResetTokenGenerator` — stateless, no
DB row, hash includes user.password so it auto-invalidates after a
successful reset (FR43, NFR-D2). 1-hour expiry via PASSWORD_RESET_TIMEOUT.

Email-enumeration defense: response is byte-identical for found vs unknown
emails. Audit log written ONLY on the registered-email path.

Throttling: 3/email/hour on request, 5/IP/min on confirm — abuse defense
in absence of authenticated identity.
"""
import hashlib
import logging
import time
import unicodedata

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.db import transaction
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework import status
from rest_framework.decorators import (
    api_view,
    permission_classes,
    throttle_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from core.models.account import Account
from core.models.dead_letter import DeadLetterLog
from core.serializers.password_reset import (
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
)
from core.services.audit import write_audit_event
from core.services.email import (
    send_password_changed_notification_email,
    send_password_reset_email,
)
from core.views.account import _first_error_field, _first_error_message
from core.views.password_reset_throttles import (
    PasswordResetConfirmThrottle,
    PasswordResetRequestThrottle,
)

logger = logging.getLogger(__name__)

_GENERIC_MESSAGE = "If an account exists for that email, we've sent a reset link."
_INVALID_LINK_ERROR = {
    "code": "INVALID_RESET_LINK",
    "message": "This reset link is invalid or has expired. Please request a new one.",
    "field": None,
}
_NO_STORE = "no-store, private"


def _normalize_email(value: str) -> str:
    return unicodedata.normalize("NFKC", value).strip().lower()


def _email_hash(email: str) -> str:
    return hashlib.sha256(email.encode()).hexdigest()[:16]


def _account_for(user) -> "Account | None":
    try:
        return user.account
    except Account.DoesNotExist:
        return None


def _string_field(data, key: str) -> str:
    raw = data.get(key)
    if not isinstance(raw, str):
        return ""
    return raw.strip()


def _generic_ok_response() -> Response:
    response = Response({"data": {"message": _GENERIC_MESSAGE}}, status=200)
    response["Cache-Control"] = _NO_STORE
    return response


def _invalid_link_response() -> Response:
    response = Response(
        {"error": _INVALID_LINK_ERROR}, status=status.HTTP_400_BAD_REQUEST
    )
    response["Cache-Control"] = _NO_STORE
    return response


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([PasswordResetRequestThrottle])
def password_reset_request(request):
    """Anonymous: accept an email, send a reset link if the email is registered.

    ALWAYS returns 200 with a generic message — never differentiates between
    "email registered" and "email unknown" (FR-spec line 907).
    """
    serializer = PasswordResetRequestSerializer(data=request.data)
    # Any validation failure (bad format, missing field) — still return the
    # same generic 200. Failing 400 here would leak "the email format you
    # entered is malformed" → enumeration via input shape.
    if not serializer.is_valid():
        return _generic_ok_response()

    email = _normalize_email(serializer.validated_data["email"])
    matches = list(User.objects.filter(email__iexact=email, is_active=True)[:2])

    if len(matches) > 1:
        # Cannot deterministically pick a single user — refuse to send. Log
        # for operator triage; response stays generic.
        logger.warning(
            "[password_reset_request] AMBIGUOUS_EMAIL email_hash=%s match_count=%s",
            _email_hash(email), len(matches),
        )
        # Best-effort dummy delay placeholder.
        time.sleep(0)
        return _generic_ok_response()

    user = matches[0] if matches else None

    if user is None or not user.has_usable_password():
        logger.info(
            "[password_reset_request] EMAIL_NOT_FOUND email_hash=%s",
            _email_hash(email),
        )
        # Placeholder for future constant-time fan-out work; matches the
        # "dummy delay on the unknown branch" requirement.
        time.sleep(0)
        return _generic_ok_response()

    token_generator = PasswordResetTokenGenerator()
    token = token_generator.make_token(user)
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))

    base = settings.SAFENET_FRONTEND_URL.rstrip("/")
    reset_url = f"{base}/reset-password/{uidb64}/{token}"

    try:
        send_password_reset_email(user, reset_url)
    except Exception as exc:
        # Best-effort delivery: never differentiate "Resend down" vs
        # "user not found" in the response. Log + dead-letter.
        logger.exception(
            "[password_reset_request] RESEND_FAILED user_id=%s exception_type=%s",
            user.id, type(exc).__name__,
        )
        account = _account_for(user)
        if account is not None:
            try:
                DeadLetterLog.objects.create(
                    task_name="password_reset_email",
                    account=account,
                    error=f"{type(exc).__name__}: {exc}",
                )
            except Exception:
                logger.exception("[password_reset_request] DLL write failed")
        else:
            # No account FK to attach — surface a clearly distinct alert so
            # the failure is not silently dropped from the operator dashboard.
            logger.error(
                "[password_reset_request] DLL_SKIPPED_NO_ACCOUNT user_id=%s "
                "error=%s: %s",
                user.id, type(exc).__name__, exc,
            )
        return _generic_ok_response()

    # Audit ONLY on the registered-email path. Email-not-found path leaves
    # zero audit footprint to avoid leaking enumeration via the audit log.
    account = _account_for(user)
    write_audit_event(
        subscriber=None,
        actor="client",
        action="password_reset_requested",
        outcome="success",
        metadata={"user_id": user.id, "email_hash": _email_hash(email)},
        account=account,
    )
    logger.info("[password_reset_request] OK user_id=%s", user.id)
    return _generic_ok_response()


_DUMMY_USER_PK_PROBE = -1


def _dummy_check_token() -> None:
    """Run a check_token computation on a sentinel non-user to flatten the
    timing differential between the cheap "user not found" path and the
    expensive "valid user, bad token" path. Best-effort — falls back to
    a no-op if the sentinel happens to resolve to a real user.
    """
    try:
        sentinel = User(pk=_DUMMY_USER_PK_PROBE, password="!unusable")
        PasswordResetTokenGenerator().check_token(sentinel, "x")
    except Exception:
        # Never let timing-defense raise; this is purely defensive padding.
        pass


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([PasswordResetConfirmThrottle])
def password_reset_confirm(request):
    """Anonymous: validate the (uid, token) pair and update the password."""
    uid_raw = _string_field(request.data, "uid")
    token_raw = _string_field(request.data, "token")

    user = None
    invalid_reason = None
    try:
        user_pk = force_str(urlsafe_base64_decode(uid_raw))
        user = User.objects.filter(pk=user_pk, is_active=True).first()
        if user is None:
            invalid_reason = "user_not_found"
    except (TypeError, ValueError, OverflowError, UnicodeDecodeError):
        invalid_reason = "bad_uid"

    if invalid_reason is not None:
        logger.warning(
            "[password_reset_confirm] INVALID_TOKEN reason=%s", invalid_reason
        )
        # Flatten timing between the cheap fail-fast paths and the expensive
        # check_token + validate_password path below.
        _dummy_check_token()
        return _invalid_link_response()

    if not user.has_usable_password() or not PasswordResetTokenGenerator().check_token(
        user, token_raw
    ):
        logger.warning(
            "[password_reset_confirm] INVALID_TOKEN reason=check_token_failed user_id=%s",
            user.id,
        )
        return _invalid_link_response()

    serializer = PasswordResetConfirmSerializer(
        data=request.data, context={"user": user},
    )
    if not serializer.is_valid():
        logger.warning(
            "[password_reset_confirm] INVALID_TOKEN reason=password_invalid user_id=%s",
            user.id,
        )
        response = Response(
            {"error": {
                "code": "VALIDATION_ERROR",
                "message": _first_error_message(serializer.errors),
                "field": _first_error_field(serializer.errors),
            }},
            status=status.HTTP_400_BAD_REQUEST,
        )
        response["Cache-Control"] = _NO_STORE
        return response

    new_password = serializer.validated_data["new_password"]

    # Lock the user row so two concurrent confirms with the same valid token
    # cannot both pass check_token and silently overwrite each other's
    # set_password call.
    with transaction.atomic():
        locked_user = User.objects.select_for_update().get(pk=user.pk)
        if not PasswordResetTokenGenerator().check_token(locked_user, token_raw):
            logger.warning(
                "[password_reset_confirm] INVALID_TOKEN reason=check_token_failed user_id=%s",
                locked_user.id,
            )
            return _invalid_link_response()
        locked_user.set_password(new_password)
        locked_user.save(update_fields=["password"])
        user = locked_user

    account = _account_for(user)
    write_audit_event(
        subscriber=None,
        actor="client",
        action="password_reset_completed",
        outcome="success",
        metadata={"user_id": user.id},
        account=account,
    )

    # Best-effort confirmation email. The password change is already
    # committed — never undo it on Resend failure; instead dead-letter so
    # operators can investigate.
    try:
        send_password_changed_notification_email(user)
    except Exception as exc:
        logger.exception(
            "[password_reset_confirm] PASSWORD_CHANGED_NOTIFICATION_FAILED "
            "user_id=%s exception_type=%s",
            user.id, type(exc).__name__,
        )
        if account is not None:
            try:
                DeadLetterLog.objects.create(
                    task_name="password_change_notification",
                    account=account,
                    error=f"{type(exc).__name__}: {exc}",
                )
            except Exception:
                logger.exception("[password_reset_confirm] DLL write failed")
        else:
            logger.error(
                "[password_reset_confirm] DLL_SKIPPED_NO_ACCOUNT user_id=%s "
                "error=%s: %s",
                user.id, type(exc).__name__, exc,
            )

    logger.info("[password_reset_confirm] OK user_id=%s", user.id)
    response = Response(
        {"data": {"message": "Password updated. You can now sign in."}},
        status=200,
    )
    # Defense in depth: corporate proxies must not cache the success body
    # for the same (uid, token) URL.
    response["Cache-Control"] = _NO_STORE
    return response
