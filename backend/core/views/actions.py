from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.engine.processor import get_recovery_action
from core.models.pending_action import PendingAction, STATUS_PENDING, STATUS_APPROVED, STATUS_EXCLUDED
from core.models.subscriber import Subscriber, SubscriberFailure
from core.serializers.actions import PendingActionSerializer
from core.services.audit import write_audit_event
from core.services.recovery import execute_recovery_action


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def pending_action_list(request):
    """GET /api/v1/actions/pending/ — list pending actions for review."""
    account = request.user.account

    actions = (
        PendingAction.objects
        .for_account(account.id)
        .filter(status=STATUS_PENDING)
        .select_related("subscriber", "failure")
        .order_by("-created_at")
    )

    serializer = PendingActionSerializer(actions, many=True)
    return Response({"data": serializer.data, "meta": {"total": actions.count()}})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def batch_approve_actions(request):
    """POST /api/v1/actions/batch/ — approve and execute selected pending actions."""
    account = request.user.account
    action_ids = request.data.get("action_ids", [])

    if not action_ids:
        return Response(
            {"error": {"code": "MISSING_IDS", "message": "action_ids is required.", "field": "action_ids"}},
            status=400,
        )

    actions = (
        PendingAction.objects
        .for_account(account.id)
        .filter(id__in=action_ids, status=STATUS_PENDING)
        .select_related("failure", "failure__subscriber", "subscriber")
    )

    approved, failed, failures = 0, 0, []
    for action in actions:
        try:
            decision = get_recovery_action(
                action.failure.decline_code,
                payment_method_country=action.failure.payment_method_country,
            )
            execute_recovery_action(action.failure, decision, account)
            action.status = STATUS_APPROVED
            action.save(update_fields=["status"])
            approved += 1
        except Exception as exc:
            failed += 1
            failures.append({"id": action.id, "error": str(exc)})

    write_audit_event(
        subscriber=None,
        actor="client",
        action="batch_actions_approved",
        outcome="success",
        metadata={"approved": approved, "failed": failed},
        account=account,
    )

    return Response({"data": {"approved": approved, "failed": failed, "failures": failures}})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def exclude_subscriber(request, subscriber_id):
    """POST /api/v1/subscribers/{id}/exclude/ — exclude subscriber from automation."""
    account = request.user.account

    try:
        subscriber = Subscriber.objects.for_account(account.id).get(id=subscriber_id)
    except Subscriber.DoesNotExist:
        return Response(
            {"error": {"code": "NOT_FOUND", "message": "Subscriber not found.", "field": None}},
            status=404,
        )

    subscriber.excluded_from_automation = True
    subscriber.save(update_fields=["excluded_from_automation"])

    # Mark all pending actions as excluded
    PendingAction.objects.for_account(account.id).filter(
        subscriber=subscriber,
        status=STATUS_PENDING,
    ).update(status=STATUS_EXCLUDED)

    # Clear pending retries
    SubscriberFailure.objects.for_account(account.id).filter(
        subscriber=subscriber,
        next_retry_at__isnull=False,
    ).update(next_retry_at=None)

    write_audit_event(
        subscriber=str(subscriber.id),
        actor="client",
        action="subscriber_excluded",
        outcome="success",
        metadata={"subscriber_id": subscriber.id},
        account=account,
    )

    return Response({"data": {"excluded": True, "subscriber_id": subscriber.id}})
