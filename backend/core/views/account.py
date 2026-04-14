from django.db import transaction
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from django.core.cache import cache
from django.utils import timezone

from core.serializers.account import CompleteProfileSerializer
from core.services.audit import write_audit_event
from core.services.tier import get_polling_frequency, is_engine_active


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def account_detail(request):
    """Returns the authenticated user's account including tier info."""
    try:
        account = request.user.account
    except request.user.__class__.account.RelatedObjectDoesNotExist:
        raise NotFound("No account associated with this user.")

    return Response(_build_account_response(account, request.user))


class _ProfileThrottle(ScopedRateThrottle):
    scope = "profile"


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([_ProfileThrottle])
def complete_profile(request):
    """
    One-time profile completion after Stripe OAuth.
    Sets user name, company name, and password.
    """
    try:
        account = request.user.account
    except request.user.__class__.account.RelatedObjectDoesNotExist:
        raise NotFound("No account associated with this user.")

    if account.profile_complete:
        return Response(
            {"error": {"code": "PROFILE_ALREADY_COMPLETED", "message": "Profile has already been set up.", "field": None}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    serializer = CompleteProfileSerializer(data=request.data, context={"user": request.user})
    if not serializer.is_valid():
        return Response(
            {"error": {
                "code": "VALIDATION_ERROR",
                "message": _first_error_message(serializer.errors),
                "field": _first_error_field(serializer.errors),
            }},
            status=status.HTTP_400_BAD_REQUEST,
        )

    data = serializer.validated_data
    user = request.user

    with transaction.atomic():
        # Re-fetch with row lock to prevent concurrent profile completion
        from core.models.account import Account
        account = Account.objects.select_for_update().get(pk=account.pk)

        if account.profile_complete:
            return Response(
                {"error": {"code": "PROFILE_ALREADY_COMPLETED", "message": "Profile has already been set up.", "field": None}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.first_name = data["first_name"]
        user.last_name = data["last_name"]
        user.set_password(data["password"])
        user.save()

        account.company_name = data["company_name"]
        account.save(update_fields=["company_name"])

    write_audit_event(
        subscriber=None,
        actor="client",
        action="profile_completed",
        outcome="success",
        account=account,
    )

    return Response(_build_account_response(account, user))


def _build_account_response(account, user) -> dict:
    """Build the standard account detail response dict."""
    has_stripe = hasattr(account, "stripe_connection")

    trial_days_remaining = None
    if account.is_on_trial and account.trial_ends_at:
        trial_days_remaining = max(0, (account.trial_ends_at - timezone.now()).days)

    next_scan_at = None
    from core.models.account import TIER_FREE
    from core.tasks.polling import POLL_LAST_RUN_KEY
    if account.tier == TIER_FREE:
        poll_cache_key = POLL_LAST_RUN_KEY.format(account_id=account.id)
        last_poll = cache.get(poll_cache_key)
        from datetime import timedelta
        if last_poll:
            next_scan_at = (last_poll + timedelta(seconds=get_polling_frequency(account))).isoformat()
        else:
            next_scan_at = (timezone.now() + timedelta(seconds=get_polling_frequency(account))).isoformat()

    return {
        "data": {
            "id": account.id,
            "owner_email": user.email,
            "owner": {
                "id": user.id,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
            },
            "company_name": account.company_name,
            "tier": account.tier,
            "trial_ends_at": account.trial_ends_at.isoformat() if account.trial_ends_at else None,
            "is_on_trial": account.is_on_trial,
            "trial_days_remaining": trial_days_remaining,
            "next_scan_at": next_scan_at,
            "engine_active": is_engine_active(account),
            "stripe_connected": has_stripe,
            "profile_complete": account.profile_complete,
            "dpa_accepted": account.dpa_accepted,
            "dpa_accepted_at": account.dpa_accepted_at.isoformat() if account.dpa_accepted_at else None,
            "engine_mode": account.engine_mode,
            "created_at": account.created_at.isoformat(),
        }
    }


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def accept_dpa(request):
    """Accept the Data Processing Agreement for the authenticated account."""
    try:
        account = request.user.account
    except request.user.__class__.account.RelatedObjectDoesNotExist:
        raise NotFound("No account associated with this user.")

    accepted_now = False
    with transaction.atomic():
        from core.models.account import Account, TIER_FREE
        account = Account.objects.select_for_update().get(pk=account.pk)

        if account.tier == TIER_FREE:
            return Response(
                {"error": {"code": "TIER_NOT_ELIGIBLE", "message": "Free-tier accounts cannot accept the DPA. Please upgrade first."}},
                status=status.HTTP_403_FORBIDDEN,
            )

        if account.dpa_accepted:
            pass  # idempotent — skip write and audit
        else:
            account.dpa_accepted_at = timezone.now()
            account.save(update_fields=["dpa_accepted_at"])
            accepted_now = True

            write_audit_event(
                subscriber=None,
                actor="client",
                action="dpa_accepted",
                outcome="success",
                account=account,
            )

    return Response(_build_account_response(account, request.user))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def set_engine_mode(request):
    """Set or switch the recovery engine mode (autopilot/supervised)."""
    try:
        account = request.user.account
    except request.user.__class__.account.RelatedObjectDoesNotExist:
        raise NotFound("No account associated with this user.")

    mode = request.data.get("mode")
    if mode not in ("autopilot", "supervised"):
        return Response(
            {"error": {"code": "INVALID_MODE", "message": "Mode must be 'autopilot' or 'supervised'."}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    old_mode = None
    changed = False
    with transaction.atomic():
        from core.models.account import Account, TIER_FREE, TIER_MID, TIER_PRO
        account = Account.objects.select_for_update().get(pk=account.pk)

        if account.tier not in (TIER_MID, TIER_PRO):
            return Response(
                {"error": {"code": "TIER_NOT_ELIGIBLE", "message": "Engine mode is only available for Mid and Pro tier accounts."}},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not account.dpa_accepted:
            return Response(
                {"error": {"code": "DPA_NOT_ACCEPTED", "message": "You must accept the Data Processing Agreement before activating the engine."}},
                status=status.HTTP_403_FORBIDDEN,
            )

        old_mode = account.engine_mode

        if old_mode == mode:
            pass  # idempotent — no change needed
        else:
            account.engine_mode = mode
            account.save(update_fields=["engine_mode"])
            changed = True

            cache.delete(f"dashboard_summary_{account.id}")

            if old_mode is None:
                write_audit_event(
                    subscriber=None,
                    actor="client",
                    action="engine_activated",
                    outcome="success",
                    metadata={"mode": mode},
                    account=account,
                )
            else:
                write_audit_event(
                    subscriber=None,
                    actor="client",
                    action="engine_mode_switched",
                    outcome="success",
                    metadata={"from": old_mode, "to": mode},
                    account=account,
                )

    return Response(_build_account_response(account, request.user))


def _first_error_message(errors: dict) -> str:
    for field, messages in errors.items():
        if isinstance(messages, list):
            return str(messages[0])
        if isinstance(messages, dict):
            for sub_messages in messages.values():
                if isinstance(sub_messages, list):
                    return str(sub_messages[0])
    return "Validation error."


def _first_error_field(errors: dict) -> str | None:
    for field in errors:
        if field == "non_field_errors":
            continue
        return field
    return None
