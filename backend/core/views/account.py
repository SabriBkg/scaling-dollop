"""
Account CRUD stub — Story 2.x will implement full account management endpoints.
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def account_detail(request):
    """Returns the authenticated user's account. Stub — full implementation in Story 2.x."""
    try:
        account = request.user.account
    except request.user.__class__.account.RelatedObjectDoesNotExist:
        raise NotFound("No account associated with this user.")
    return Response({
        "id": account.id,
        "owner_email": request.user.email,
    })
