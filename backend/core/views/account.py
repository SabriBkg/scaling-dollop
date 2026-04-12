from django.db import transaction
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from core.serializers.account import CompleteProfileSerializer
from core.services.audit import write_audit_event


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def account_detail(request):
    """Returns the authenticated user's account including tier info."""
    try:
        account = request.user.account
    except request.user.__class__.account.RelatedObjectDoesNotExist:
        raise NotFound("No account associated with this user.")

    has_stripe = hasattr(account, "stripe_connection")

    return Response({
        "data": {
            "id": account.id,
            "owner_email": request.user.email,
            "owner": {
                "id": request.user.id,
                "email": request.user.email,
                "first_name": request.user.first_name,
                "last_name": request.user.last_name,
            },
            "company_name": account.company_name,
            "tier": account.tier,
            "trial_ends_at": account.trial_ends_at.isoformat() if account.trial_ends_at else None,
            "is_on_trial": account.is_on_trial,
            "stripe_connected": has_stripe,
            "profile_complete": account.profile_complete,
            "created_at": account.created_at.isoformat(),
        }
    })


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

    has_stripe = hasattr(account, "stripe_connection")

    return Response({
        "data": {
            "id": account.id,
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
            "stripe_connected": has_stripe,
            "profile_complete": account.profile_complete,
            "created_at": account.created_at.isoformat(),
        }
    })


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
