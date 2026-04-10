from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


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
            "tier": account.tier,
            "trial_ends_at": account.trial_ends_at.isoformat() if account.trial_ends_at else None,
            "is_on_trial": account.is_on_trial,
            "stripe_connected": has_stripe,
            "created_at": account.created_at.isoformat(),
        }
    })
