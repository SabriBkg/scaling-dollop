"""Story 3.3 v1 — client-triggered dunning email + manual resolve views.

Both endpoints are subscriber-scoped client actions. Live in their own
module per architecture.md "one route, one file" preference for v1
endpoints (actions.py is the v0 PendingAction batch view).
"""
from django.db import transaction
from django_fsm import TransitionNotAllowed
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle

from core.engine.state_machine import STATUS_ACTIVE
from core.models.account import TIER_FREE
from core.models.notification import NotificationOptOut
from core.models.subscriber import Subscriber, SubscriberFailure
from core.services.audit import write_audit_event
from core.services.dpa import require_dpa_accepted
from core.tasks.notifications import CLIENT_MANUAL_EMAIL_TYPES, send_dunning_email


class _SendEmailThrottle(SimpleRateThrottle):
    """Per-user throttle for the manual send-email endpoint.

    Subclasses SimpleRateThrottle (not ScopedRateThrottle) because the latter
    overwrites self.scope from view.throttle_scope at allow_request() time —
    which is None for @api_view function views and silently disables throttling.
    """
    scope = "send_email"

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}


class _MarkResolvedThrottle(SimpleRateThrottle):
    """Per-user throttle for the manual mark-resolved endpoint. See _SendEmailThrottle."""
    scope = "mark_resolved"

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([_SendEmailThrottle])
def send_email(request, subscriber_id: int):
    """POST /api/v1/subscribers/{id}/send-email/ — queue a client-triggered dunning email."""
    try:
        account = request.user.account
    except request.user.__class__.account.RelatedObjectDoesNotExist:
        return Response(
            {"error": {"code": "NOT_FOUND", "message": "No account found.", "field": None}},
            status=status.HTTP_404_NOT_FOUND,
        )

    # 1. DPA gate — must be FIRST (per dpa.py docstring & 3-1-v1 contract)
    dpa_response = require_dpa_accepted(account)
    if dpa_response is not None:
        return dpa_response

    # 2. Tier gate — Free is view-only
    if account.tier == TIER_FREE:
        return Response(
            {"error": {
                "code": "TIER_REQUIRED",
                "message": "Upgrade to Mid or Pro to enable email actions.",
                "field": None,
            }},
            status=status.HTTP_403_FORBIDDEN,
        )

    # 3. Validate body
    email_type = request.data.get("email_type")
    failure_id = request.data.get("failure_id")
    if email_type not in CLIENT_MANUAL_EMAIL_TYPES:
        return Response(
            {"error": {
                "code": "VALIDATION_ERROR",
                "message": f"email_type must be one of {list(CLIENT_MANUAL_EMAIL_TYPES)}.",
                "field": "email_type",
            }},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not isinstance(failure_id, int) or isinstance(failure_id, bool):
        return Response(
            {"error": {
                "code": "VALIDATION_ERROR",
                "message": "failure_id must be an integer.",
                "field": "failure_id",
            }},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # 4. Tenant-scoped lookups
    try:
        subscriber = Subscriber.objects.for_account(account.id).get(id=subscriber_id)
    except Subscriber.DoesNotExist:
        return Response(
            {"error": {"code": "NOT_FOUND", "message": "Subscriber not found.", "field": None}},
            status=status.HTTP_404_NOT_FOUND,
        )

    try:
        failure = SubscriberFailure.objects.for_account(account.id).get(
            id=failure_id, subscriber_id=subscriber.id,
        )
    except SubscriberFailure.DoesNotExist:
        return Response(
            {"error": {"code": "NOT_FOUND", "message": "Failure not found for this subscriber.", "field": "failure_id"}},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Subscriber must still be ACTIVE — symmetric with Gate 6 in _passes_gates.
    # Sending dunning to recovered/passive_churn/fraud_flagged is non-sensical
    # for all three CLIENT_MANUAL_EMAIL_TYPES.
    if subscriber.status != STATUS_ACTIVE:
        return Response(
            {"error": {
                "code": "INVALID_STATE",
                "message": f"Cannot send email — subscriber status is '{subscriber.status}'.",
                "field": None,
            }},
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    # 5. Opt-out check at view boundary (so client gets a clear 422,
    #    not a silent suppression in the task)
    sub_email = (subscriber.email or "").strip().lower()
    if sub_email and NotificationOptOut.objects.for_account(account.id).filter(
        subscriber_email__iexact=sub_email,
    ).exists():
        write_audit_event(
            subscriber=str(subscriber.id),
            actor="client",
            action="email_sent_blocked",
            outcome="skipped",
            metadata={"reason": "opt_out", "email_type": email_type, "failure_id": failure_id},
            account=account,
        )
        return Response(
            {"error": {"code": "OPT_OUT", "message": "Subscriber has opted out of notifications.", "field": None}},
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    # 6. Exclusion check
    if subscriber.excluded_from_automation:
        write_audit_event(
            subscriber=str(subscriber.id),
            actor="client",
            action="email_sent_blocked",
            outcome="skipped",
            metadata={"reason": "excluded", "email_type": email_type, "failure_id": failure_id},
            account=account,
        )
        return Response(
            {"error": {"code": "EXCLUDED", "message": "Subscriber is excluded from automation.", "field": None}},
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    # 7. Enqueue task + write client-trigger audit (records intent)
    send_dunning_email.delay(failure_id, email_type)
    write_audit_event(
        subscriber=str(subscriber.id),
        actor="client",
        action="email_sent",
        outcome="success",
        metadata={"email_type": email_type, "trigger": "client_manual", "failure_id": failure_id},
        account=account,
    )
    return Response(
        {"data": {"queued": True, "email_type": email_type, "failure_id": failure_id}},
        status=status.HTTP_202_ACCEPTED,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([_MarkResolvedThrottle])
def mark_resolved(request, subscriber_id: int):
    """POST /api/v1/subscribers/{id}/mark-resolved/ — manually mark as Recovered."""
    try:
        account = request.user.account
    except request.user.__class__.account.RelatedObjectDoesNotExist:
        return Response(
            {"error": {"code": "NOT_FOUND", "message": "No account found.", "field": None}},
            status=status.HTTP_404_NOT_FOUND,
        )

    # DPA + tier gates (parity with send_email — Mark resolved is also paid)
    dpa_response = require_dpa_accepted(account)
    if dpa_response is not None:
        return dpa_response
    if account.tier == TIER_FREE:
        return Response(
            {"error": {
                "code": "TIER_REQUIRED",
                "message": "Upgrade to Mid or Pro to enable email actions.",
                "field": None,
            }},
            status=status.HTTP_403_FORBIDDEN,
        )

    # Lock the row + run the FSM transition + audit write in one atomic block:
    # select_for_update() prevents two concurrent calls from both reading
    # prior_status=active and both transitioning. The post_transition signal
    # writes a status_<target> audit row — if subscriber.save() then raised,
    # transaction.atomic() rolls both back together.
    with transaction.atomic():
        try:
            subscriber = (
                Subscriber.objects.for_account(account.id)
                .select_for_update()
                .get(id=subscriber_id)
            )
        except Subscriber.DoesNotExist:
            return Response(
                {"error": {"code": "NOT_FOUND", "message": "Subscriber not found.", "field": None}},
                status=status.HTTP_404_NOT_FOUND,
            )

        prior_status = subscriber.status
        try:
            subscriber.mark_resolved_manually()
        except TransitionNotAllowed:
            return Response(
                {"error": {
                    "code": "INVALID_TRANSITION",
                    "message": f"Cannot mark resolved from status '{prior_status}'.",
                    "field": None,
                }},
                status=status.HTTP_400_BAD_REQUEST,
            )
        subscriber.save(update_fields=["status"])

        write_audit_event(
            subscriber=str(subscriber.id),
            actor="client",
            action="manual_resolved",
            outcome="success",
            metadata={"trigger": "client_manual", "from": prior_status},
            account=account,
        )
    return Response(
        {"data": {
            "resolved": True,
            "subscriber_id": subscriber.id,
            "from_status": prior_status,
            "to_status": "recovered",
        }},
        status=status.HTTP_200_OK,
    )
