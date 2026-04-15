from django.core.cache import cache
from django.db.models import Count, Sum, Q
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.engine.labels import DECLINE_CODE_LABELS
from core.engine.rules import DECLINE_RULES
from core.engine.state_machine import STATUS_RECOVERED, STATUS_FRAUD_FLAGGED
from core.models.pending_action import PendingAction, STATUS_PENDING
from core.models.subscriber import Subscriber, SubscriberFailure
from core.serializers.dashboard import DashboardSummarySerializer

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
    attention_items = []

    # Fraud-flagged subscribers
    fraud_subs = Subscriber.objects.for_account(account_id).filter(
        status=STATUS_FRAUD_FLAGGED,
    )
    for sub in fraud_subs:
        attention_items.append({
            "type": "fraud_flag",
            "subscriber_id": sub.id,
            "subscriber_name": sub.email or sub.stripe_customer_id,
            "label": f"Fraud flagged: {sub.email or sub.stripe_customer_id}",
        })

    # Pending actions (supervised mode)
    pending_actions = (
        PendingAction.objects.for_account(account_id)
        .filter(status=STATUS_PENDING)
        .select_related("subscriber")
    )
    for pa in pending_actions:
        sub = pa.subscriber
        attention_items.append({
            "type": "pending_action",
            "subscriber_id": sub.id,
            "subscriber_name": sub.email or sub.stripe_customer_id,
            "label": f"Pending approval: {sub.email or sub.stripe_customer_id}",
        })

    # Retry cap approaching (retry_count >= retry_cap - 1, where retry_cap > 0)
    for failure in (
        SubscriberFailure.objects.for_account(account_id)
        .filter(subscriber__status="active")
        .select_related("subscriber")
    ):
        rule = DECLINE_RULES.get(failure.decline_code, DECLINE_RULES.get("_default"))
        if rule and rule["retry_cap"] > 0 and failure.retry_count >= rule["retry_cap"] - 1:
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
