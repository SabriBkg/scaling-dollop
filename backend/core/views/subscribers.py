from django.db.models import Subquery, OuterRef, BooleanField, Value, Case, When, Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.engine.labels import DECLINE_CODE_LABELS
from core.models.pending_action import PendingAction, STATUS_PENDING
from core.models.subscriber import Subscriber, SubscriberFailure
from core.serializers.subscribers import SubscriberCardSerializer


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def subscriber_list(request):
    """Returns subscriber cards for the authenticated user's account."""
    try:
        account = request.user.account
    except request.user.__class__.account.RelatedObjectDoesNotExist:
        return Response(
            {"error": {"code": "NOT_FOUND", "message": "No account found.", "field": None}},
            status=404,
        )

    # Subquery: latest failure's decline_code for each subscriber
    latest_failure = (
        SubscriberFailure.objects.filter(subscriber_id=OuterRef("pk"))
        .order_by("-failure_created_at")
    )

    # Subquery: check if subscriber has a pending action
    has_pending = (
        PendingAction.objects.filter(
            subscriber_id=OuterRef("pk"),
            status=STATUS_PENDING,
        )
        .values("pk")[:1]
    )

    subscribers = (
        Subscriber.objects.for_account(account.id)
        .filter(failures__isnull=False)
        .distinct()
        .annotate(
            latest_decline_code=Subquery(latest_failure.values("decline_code")[:1]),
            latest_amount_cents=Subquery(latest_failure.values("amount_cents")[:1]),
            has_pending_action=Case(
                When(Q(pk__in=Subquery(
                    PendingAction.objects.filter(
                        status=STATUS_PENDING,
                    ).values("subscriber_id")
                )), then=Value(True)),
                default=Value(False),
                output_field=BooleanField(),
            ),
        )
        .order_by(
            # Attention-first: fraud_flagged status OR has pending action
            Case(
                When(status="fraud_flagged", then=Value(0)),
                When(has_pending_action=True, then=Value(0)),
                default=Value(1),
            ),
            "-updated_at",
        )
    )

    results = []
    for sub in subscribers:
        decline_code = sub.latest_decline_code
        results.append({
            "id": sub.id,
            "stripe_customer_id": sub.stripe_customer_id,
            "email": sub.email,
            "status": sub.status,
            "decline_code": decline_code,
            "decline_reason": DECLINE_CODE_LABELS.get(
                decline_code, DECLINE_CODE_LABELS["_default"]
            ) if decline_code else None,
            "amount_cents": sub.latest_amount_cents,
            "needs_attention": sub.status == "fraud_flagged" or sub.has_pending_action,
            "excluded_from_automation": sub.excluded_from_automation,
        })

    serializer = SubscriberCardSerializer(results, many=True)
    return Response({"data": serializer.data})
