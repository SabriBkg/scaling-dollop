"""Story 3.4 v1 — bulk dunning email dispatch view.

POST /api/v1/subscribers/batch-send-email/ — fan-out per-selection enqueue.
Mirrors the per-row send_email contract (DPA → tier → validation → tenant →
opt-out → exclusion → enqueue) for each entry in a list of selections, with
partial-failure semantics (a single bad row does NOT abort the batch).
"""
import logging

from kombu.exceptions import OperationalError as KombuOperationalError
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

logger = logging.getLogger(__name__)


MAX_BATCH_SIZE = 100


class _BatchSendEmailThrottle(SimpleRateThrottle):
    """Per-user throttle for the bulk dunning send endpoint.

    Subclasses SimpleRateThrottle (not ScopedRateThrottle) — DRF's
    ScopedRateThrottle.allow_request overwrites self.scope from
    view.throttle_scope, which is None for @api_view function views,
    silently disabling the throttle. See Story 3.3 v1 debug log.
    """
    scope = "batch_send_email"

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([_BatchSendEmailThrottle])
def batch_send_email(request):
    """POST /api/v1/subscribers/batch-send-email/ — fan-out per-selection enqueue."""
    try:
        account = request.user.account
    except request.user.__class__.account.RelatedObjectDoesNotExist:
        return Response(
            {"error": {"code": "NOT_FOUND", "message": "No account found.", "field": None}},
            status=status.HTTP_404_NOT_FOUND,
        )

    # 1. DPA gate — FIRST, so unsigned accounts get DPA_REQUIRED, not VALIDATION_ERROR.
    dpa_response = require_dpa_accepted(account)
    if dpa_response is not None:
        return dpa_response

    # 2. Tier gate — Free is view-only.
    if account.tier == TIER_FREE:
        return Response(
            {"error": {
                "code": "TIER_REQUIRED",
                "message": "Upgrade to Mid or Pro to enable email actions.",
                "field": None,
            }},
            status=status.HTTP_403_FORBIDDEN,
        )

    # 3. Body shape validation
    selections = request.data.get("selections")
    if not isinstance(selections, list) or not selections:
        return _validation("selections must be a non-empty list.", "selections")
    if len(selections) > MAX_BATCH_SIZE:
        return _validation(
            f"Maximum {MAX_BATCH_SIZE} selections per batch.", "selections",
        )

    # 4. Per-entry shape validation — strict types, no booleans-as-int.
    for i, sel in enumerate(selections):
        if not isinstance(sel, dict):
            return _validation(
                f"selections[{i}] must be an object.", f"selections[{i}]",
            )
        sid = sel.get("subscriber_id")
        fid = sel.get("failure_id")
        etype = sel.get("email_type")
        if not isinstance(sid, int) or isinstance(sid, bool):
            return _validation(
                "subscriber_id must be an integer.",
                f"selections[{i}].subscriber_id",
            )
        if not isinstance(fid, int) or isinstance(fid, bool):
            return _validation(
                "failure_id must be an integer.",
                f"selections[{i}].failure_id",
            )
        if etype not in CLIENT_MANUAL_EMAIL_TYPES:
            return _validation(
                f"email_type must be one of {list(CLIENT_MANUAL_EMAIL_TYPES)}.",
                f"selections[{i}].email_type",
            )

    # 5. Per-selection processing — collect failures, enqueue successes.
    queued = 0
    failed = 0
    failures: list[dict] = []
    for sel in selections:
        outcome = _process_one_selection(
            account, sel["subscriber_id"], sel["failure_id"], sel["email_type"],
        )
        if outcome["ok"]:
            queued += 1
        else:
            failed += 1
            failures.append({
                "subscriber_id": sel["subscriber_id"],
                "failure_id": sel["failure_id"],
                "code": outcome["code"],
                "message": outcome["message"],
            })

    # 6. One summary audit row per request.
    summary = "success" if failed == 0 else ("partial" if queued > 0 else "failed")
    write_audit_event(
        subscriber=None,
        actor="client",
        action="batch_email_send",
        outcome=summary,
        metadata={
            "selections_total": len(selections),
            "queued": queued,
            "failed": failed,
            "trigger": "client_manual",
        },
        account=account,
    )
    return Response(
        {"data": {
            "queued": queued,
            "failed": failed,
            "failures": failures,
            "selections_total": len(selections),
        }},
        status=status.HTTP_200_OK,
    )


def _validation(message: str, field: str) -> Response:
    return Response(
        {"error": {"code": "VALIDATION_ERROR", "message": message, "field": field}},
        status=status.HTTP_400_BAD_REQUEST,
    )


def _process_one_selection(account, sid: int, fid: int, etype: str) -> dict:
    """Per-row gate sequence + enqueue. Returns {'ok': bool, 'code'?, 'message'?}.

    Per-selection processing is intentionally NOT wrapped in transaction.atomic():
    partial-failure semantics demand that successful enqueues persist their audit
    rows even if a later selection's lookup raises.
    """
    try:
        subscriber = Subscriber.objects.for_account(account.id).get(id=sid)
    except Subscriber.DoesNotExist:
        return {"ok": False, "code": "NOT_FOUND", "message": "Subscriber not found."}

    try:
        failure = SubscriberFailure.objects.for_account(account.id).get(
            id=fid, subscriber_id=subscriber.id,
        )
    except SubscriberFailure.DoesNotExist:
        return {
            "ok": False,
            "code": "NOT_FOUND",
            "message": "Failure not found for this subscriber.",
        }

    if subscriber.status != STATUS_ACTIVE:
        _audit_blocked(
            account, subscriber, fid, etype,
            reason="invalid_state",
            extra={"subscriber_status": subscriber.status},
        )
        return {
            "ok": False,
            "code": "INVALID_STATE",
            "message": f"Cannot send email — subscriber status is '{subscriber.status}'.",
        }

    sub_email = (subscriber.email or "").strip().lower()
    if sub_email and NotificationOptOut.objects.for_account(account.id).filter(
        subscriber_email__iexact=sub_email,
    ).exists():
        _audit_blocked(account, subscriber, fid, etype, reason="opt_out")
        return {
            "ok": False,
            "code": "OPT_OUT",
            "message": "Subscriber has opted out of notifications.",
        }

    if subscriber.excluded_from_automation:
        _audit_blocked(account, subscriber, fid, etype, reason="excluded")
        return {
            "ok": False,
            "code": "EXCLUDED",
            "message": "Subscriber is excluded from automation.",
        }

    try:
        send_dunning_email.delay(failure.id, etype)
    except (KombuOperationalError, OSError) as exc:
        logger.warning(
            "[batch_send_email] broker enqueue failed failure_id=%s email_type=%s error=%s",
            fid, etype, exc,
        )
        return {
            "ok": False,
            "code": "QUEUE_ERROR",
            "message": "Could not enqueue email send.",
        }

    write_audit_event(
        subscriber=str(subscriber.id),
        actor="client",
        action="email_sent",
        outcome="success",
        metadata={
            "email_type": etype,
            "trigger": "client_manual",
            "failure_id": str(fid),
            "batch": True,
        },
        account=account,
    )
    return {"ok": True}


def _audit_blocked(account, subscriber, failure_id, email_type, *, reason, extra=None):
    meta = {
        "reason": reason,
        "email_type": email_type,
        "failure_id": str(failure_id),
        "batch": True,
    }
    if extra:
        meta.update(extra)
    write_audit_event(
        subscriber=str(subscriber.id),
        actor="client",
        action="email_sent_blocked",
        outcome="skipped",
        metadata=meta,
        account=account,
    )
