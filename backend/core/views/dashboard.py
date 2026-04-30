from django.core.cache import cache
from django.db.models import Count, Sum, Q, OuterRef, Subquery, DateTimeField
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.engine.labels import DECLINE_CODE_LABELS
from core.engine.rules import DECLINE_RULES
from core.engine.state_machine import STATUS_ACTIVE, STATUS_RECOVERED, STATUS_FRAUD_FLAGGED
from core.models.notification import NotificationLog
from core.models.pending_action import PendingAction, STATUS_PENDING
from core.models.subscriber import Subscriber, SubscriberFailure
from core.serializers.dashboard import (
    DashboardSummarySerializer,
    FailedPaymentRowSerializer,
)

ATTENTION_ITEMS_CAP = 10
CACHE_TTL = 300  # 5 minutes


def _get_cache_key(account_id):
    return f"dashboard_summary_{account_id}"


# Decline codes that are NOT eligible for recovery
NON_RECOVERABLE_CODES = frozenset(
    code
    for code, rule in DECLINE_RULES.items()
    if code != "_default" and rule["action"] in ("fraud_flag", "no_action")
)


def _build_summary(account_id):
    failures = SubscriberFailure.objects.for_account(account_id)

    total_failures = failures.count()
    total_subscribers = (
        Subscriber.objects.for_account(account_id)
        .filter(failures__isnull=False)
        .distinct()
        .count()
    )

    # Estimated recoverable = sum of amounts where decline code is NOT in non-recoverable set
    estimated_recoverable_cents = (
        failures.exclude(decline_code__in=NON_RECOVERABLE_CODES)
        .aggregate(total=Sum("amount_cents"))["total"]
        or 0
    )

    # Recovered this month
    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    recovered_qs = Subscriber.objects.for_account(account_id).filter(
        status=STATUS_RECOVERED,
        updated_at__gte=month_start,
    )
    recovered_count = recovered_qs.count()

    # Sum the amounts of failures belonging to recovered subscribers this month
    recovered_this_month_cents = (
        SubscriberFailure.objects.for_account(account_id)
        .filter(
            subscriber__status=STATUS_RECOVERED,
            subscriber__updated_at__gte=month_start,
        )
        .aggregate(total=Sum("amount_cents"))["total"]
        or 0
    )

    # Recovery rate
    recovery_rate = 0
    if total_subscribers > 0:
        recovery_rate = round((recovered_count / total_subscribers) * 100, 1)

    # Net benefit = recovered - 0 (subscription cost is external, not tracked here)
    net_benefit_cents = recovered_this_month_cents

    # Decline code breakdown
    breakdown_qs = (
        failures.values("decline_code", "classified_action")
        .annotate(
            subscriber_count=Count("subscriber_id", distinct=True),
            total_amount_cents=Sum("amount_cents"),
        )
        .order_by("-subscriber_count")
    )

    decline_breakdown = []
    for entry in breakdown_qs:
        code = entry["decline_code"]
        decline_breakdown.append(
            {
                "decline_code": code,
                "human_label": DECLINE_CODE_LABELS.get(
                    code, DECLINE_CODE_LABELS["_default"]
                ),
                "subscriber_count": entry["subscriber_count"],
                "total_amount_cents": entry["total_amount_cents"] or 0,
                "recovery_action": entry["classified_action"],
            }
        )

    # Pending action count for Supervised mode badge
    pending_action_count = (
        PendingAction.objects.for_account(account_id)
        .filter(status=STATUS_PENDING)
        .count()
    )

    # Attention items: fraud flags, pending actions, retry cap approaching
    # Capped at ATTENTION_ITEMS_CAP total; priority: fraud → pending → retry_cap.
    attention_items = []
    seen_retry_cap = set()

    # Fraud-flagged subscribers
    fraud_subs = Subscriber.objects.for_account(account_id).filter(
        status=STATUS_FRAUD_FLAGGED,
    )[:ATTENTION_ITEMS_CAP]
    for sub in fraud_subs:
        attention_items.append({
            "type": "fraud_flag",
            "subscriber_id": sub.id,
            "subscriber_name": sub.email or sub.stripe_customer_id,
            "label": f"Fraud flagged: {sub.email or sub.stripe_customer_id}",
        })

    # Pending actions (supervised mode)
    if len(attention_items) < ATTENTION_ITEMS_CAP:
        pending_actions = (
            PendingAction.objects.for_account(account_id)
            .filter(status=STATUS_PENDING)
            .select_related("subscriber")
        )[: ATTENTION_ITEMS_CAP - len(attention_items)]
        for pa in pending_actions:
            sub = pa.subscriber
            attention_items.append({
                "type": "pending_action",
                "subscriber_id": sub.id,
                "subscriber_name": sub.email or sub.stripe_customer_id,
                "label": f"Pending approval: {sub.email or sub.stripe_customer_id}",
            })

    # Retry cap approaching (retry_count >= retry_cap - 1, where retry_cap > 0)
    if len(attention_items) < ATTENTION_ITEMS_CAP:
        for failure in (
            SubscriberFailure.objects.for_account(account_id)
            .filter(subscriber__status=STATUS_ACTIVE)
            .select_related("subscriber")
        ):
            if len(attention_items) >= ATTENTION_ITEMS_CAP:
                break
            rule = DECLINE_RULES.get(failure.decline_code, DECLINE_RULES.get("_default"))
            if not (rule and rule["retry_cap"] > 0 and failure.retry_count >= rule["retry_cap"] - 1):
                continue
            if failure.subscriber_id in seen_retry_cap:
                continue
            seen_retry_cap.add(failure.subscriber_id)
            attention_items.append({
                "type": "retry_cap",
                "subscriber_id": failure.subscriber_id,
                "subscriber_name": failure.subscriber.email or failure.subscriber.stripe_customer_id,
                "label": f"Retry cap approaching: {failure.subscriber.email or failure.subscriber.stripe_customer_id}",
            })

    return {
        "total_failures": total_failures,
        "total_subscribers": total_subscribers,
        "estimated_recoverable_cents": estimated_recoverable_cents,
        "recovered_this_month_cents": recovered_this_month_cents,
        "recovered_count": recovered_count,
        "recovery_rate": recovery_rate,
        "net_benefit_cents": net_benefit_cents,
        "decline_breakdown": decline_breakdown,
        "pending_action_count": pending_action_count,
        "attention_items": attention_items,
    }


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard_summary(request):
    """Returns aggregated dashboard KPIs for the authenticated user's account."""
    try:
        account = request.user.account
    except request.user.__class__.account.RelatedObjectDoesNotExist:
        return Response(
            {"error": {"code": "NOT_FOUND", "message": "No account found.", "field": None}},
            status=404,
        )

    cache_key = _get_cache_key(account.id)
    data = cache.get(cache_key)

    if data is None:
        data = _build_summary(account.id)
        cache.set(cache_key, data, CACHE_TTL)

    serializer = DashboardSummarySerializer(data)
    return Response({"data": serializer.data})


VALID_SORT_KEYS = {"date", "amount"}
VALID_SORT_DIRS = {"asc", "desc"}
SORT_FIELD_MAP = {"date": "failure_created_at", "amount": "amount_cents"}


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def failed_payments_list(request):
    """Returns current-month failed-payment rows for the authenticated user's account."""
    try:
        account = request.user.account
    except request.user.__class__.account.RelatedObjectDoesNotExist:
        return Response(
            {"error": {"code": "NOT_FOUND", "message": "No account found.", "field": None}},
            status=404,
        )

    sort = request.GET.get("sort", "date")
    direction = request.GET.get("dir", "desc")
    if sort not in VALID_SORT_KEYS:
        return Response(
            {"error": {"code": "VALIDATION_ERROR", "message": "Invalid sort param.", "field": "sort"}},
            status=400,
        )
    if direction not in VALID_SORT_DIRS:
        return Response(
            {"error": {"code": "VALIDATION_ERROR", "message": "Invalid dir param.", "field": "dir"}},
            status=400,
        )

    # v1: month boundary computed in UTC. Per-account timezone deferred to v2.
    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    last_sent = (
        NotificationLog.objects.for_account(account.id)
        .filter(
            failure_id=OuterRef("pk"),
            subscriber_id=OuterRef("subscriber_id"),
            status="sent",
        )
        .order_by("-created_at")
        .values("created_at")[:1]
    )

    failures = (
        SubscriberFailure.objects.for_account(account.id)
        .filter(failure_created_at__gte=month_start)
        .select_related("subscriber")
        .annotate(
            last_email_sent_at=Subquery(last_sent, output_field=DateTimeField())
        )
    )

    order_field = SORT_FIELD_MAP[sort]
    if direction == "desc":
        order_field = f"-{order_field}"
    failures = failures.order_by(order_field, "-id")

    results = []
    for f in failures:
        sub = f.subscriber
        results.append({
            "id": f.id,
            "subscriber_id": sub.id,
            "subscriber_email": sub.email or "",
            "subscriber_stripe_customer_id": sub.stripe_customer_id,
            "subscriber_status": sub.status,
            "decline_code": f.decline_code,
            "decline_reason": DECLINE_CODE_LABELS.get(
                f.decline_code, DECLINE_CODE_LABELS["_default"]
            ),
            "amount_cents": f.amount_cents,
            "failure_created_at": f.failure_created_at,
            # recommended_email_type set to None until Story 3.5 v1 lands the rule engine.
            "recommended_email_type": None,
            "last_email_sent_at": f.last_email_sent_at,
            "payment_method_country": f.payment_method_country,
            "excluded_from_automation": sub.excluded_from_automation,
        })

    serializer = FailedPaymentRowSerializer(results, many=True)
    return Response({"data": serializer.data})
