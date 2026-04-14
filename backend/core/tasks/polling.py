"""
Hourly polling task for new payment failures across all accounts.
Registered with Celery beat at 3600-second intervals.
"""
import logging
from datetime import timedelta

import stripe
from django.core.cache import cache
from django.utils import timezone

from safenet_backend.celery import app
from core.models.account import Account, StripeConnection, TIER_FREE
from core.services.audit import write_audit_event
from core.services.failure_ingestion import ingest_failed_payment
from core.services.tier import get_polling_frequency, is_engine_active

logger = logging.getLogger(__name__)

POLL_LAST_RUN_KEY = "poll:last_run:{account_id}"
MISSED_CYCLE_THRESHOLD_MINUTES = 90
# 48-hour TTL so cache survives extended outages without suppressing missed-cycle alerts
POLL_CACHE_TTL = 48 * 3600


@app.task(bind=True)
def poll_new_failures(self):
    """
    Dispatch per-account polling subtasks for all active accounts.
    Each account is polled in isolation so one failure cannot block others.
    """
    connections = StripeConnection.objects.select_related("account").all()
    account_ids = [conn.account_id for conn in connections]

    for account_id in account_ids:
        poll_account_failures.delay(account_id)

    logger.info("Dispatched polling subtasks for %d accounts", len(account_ids))
    return {"accounts_dispatched": len(account_ids)}


@app.task(bind=True, max_retries=5, default_retry_delay=60)
def poll_account_failures(self, account_id):
    """
    Poll a single account for new failed payment intents since last poll.
    Isolated per-account — rate limits and errors do not affect other accounts.
    """
    try:
        connection = StripeConnection.objects.select_related("account").get(account_id=account_id)
    except StripeConnection.DoesNotExist:
        logger.warning("StripeConnection not found for account %s, skipping poll", account_id)
        return {"account_id": account_id, "skipped": True}

    account = connection.account
    cache_key = POLL_LAST_RUN_KEY.format(account_id=account_id)

    # Free-tier frequency gating: skip if not due for next poll
    if account.tier == TIER_FREE:
        last_run_ts = cache.get(cache_key)
        if last_run_ts:
            freq = get_polling_frequency(account)
            elapsed = (timezone.now() - last_run_ts).total_seconds()
            if elapsed < freq:
                write_audit_event(
                    subscriber=None,
                    actor="engine",
                    action="polling_skipped_free_tier",
                    outcome="skipped",
                    account=account,
                    metadata={"account_id": account_id, "next_due_in_seconds": int(freq - elapsed)},
                )
                logger.info("Free-tier account %s not due for poll, skipping", account_id)
                return {"account_id": account_id, "skipped_free_tier": True}

    # Check for missed cycle (AC5: alert within 90 minutes)
    last_run_ts = cache.get(cache_key)
    if last_run_ts:
        elapsed_minutes = (timezone.now() - last_run_ts).total_seconds() / 60
        if elapsed_minutes > MISSED_CYCLE_THRESHOLD_MINUTES:
            write_audit_event(
                subscriber=None,
                actor="engine",
                action="polling_cycle_missed",
                outcome="alert",
                account=account,
                metadata={"gap_minutes": round(elapsed_minutes, 1), "account_id": account_id},
            )
            logger.warning(
                "Polling cycle missed for account %s — gap of %.1f minutes",
                account_id,
                elapsed_minutes,
            )

    # Determine time window
    if last_run_ts:
        created_gte = int(last_run_ts.timestamp())
    else:
        # First poll — look back 90 minutes to catch any gap
        fallback = timezone.now() - timedelta(minutes=90)
        created_gte = int(fallback.timestamp())

    access_token = connection.access_token
    total_created = 0

    try:
        payment_intents = stripe.PaymentIntent.list(
            api_key=access_token,
            created={"gte": created_gte},
            limit=100,
        )

        for pi in payment_intents.auto_paging_iter():
            if pi.status != "requires_payment_method":
                continue

            subscriber, failure, created = ingest_failed_payment(account, pi)
            if created:
                total_created += 1

                if is_engine_active(account):
                    if account.engine_mode == "autopilot":
                        _process_autopilot_recovery(failure, account)
                    elif account.engine_mode == "supervised":
                        _process_supervised_queue(failure, account)

    except stripe.StripeError as exc:
        logger.warning("Rate limited during polling for account %s, retrying", account_id)
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 30)

    # Detect card updates and trigger immediate retries (FR47)
    if is_engine_active(account):
        _detect_card_updates(account, access_token)

    # Check for subscription cancellations (AC7)
    if is_engine_active(account):
        _check_subscription_cancellations(account, access_token)

    # Mark successful poll time
    cache.set(cache_key, timezone.now(), timeout=POLL_CACHE_TTL)

    write_audit_event(
        subscriber=None,
        actor="engine",
        action="polling_cycle_completed",
        outcome="success",
        account=account,
        metadata={
            "account_id": account_id,
            "new_failures_created": total_created,
        },
    )

    return {"account_id": account_id, "new_failures": total_created}


def _process_supervised_queue(failure, account):
    """
    Queue a recovery action for client review in Supervised mode.
    Exception: fraud_flag actions execute immediately — fraud cannot wait for approval.
    """
    from core.engine.processor import get_recovery_action
    from core.engine.state_machine import ACTION_FRAUD_FLAG
    from core.models.pending_action import PendingAction
    from core.services.recovery import execute_recovery_action

    # Skip excluded subscribers
    if failure.subscriber.excluded_from_automation:
        return

    decision = get_recovery_action(
        failure.decline_code,
        payment_method_country=failure.payment_method_country,
    )

    # Fraud must execute immediately — never queue for review
    if decision.action == ACTION_FRAUD_FLAG:
        execute_recovery_action(failure, decision, account)
        return

    PendingAction.objects.create(
        account=account,
        subscriber=failure.subscriber,
        failure=failure,
        recommended_action=decision.action,
        recommended_retry_cap=decision.retry_cap,
        recommended_payday_aware=decision.payday_aware,
    )

    write_audit_event(
        subscriber=str(failure.subscriber.id),
        actor="engine",
        action="action_queued_supervised",
        outcome="success",
        metadata={
            "failure_id": str(failure.id),
            "recommended_action": decision.action,
            "decline_code": failure.decline_code,
        },
        account=account,
    )


def _process_autopilot_recovery(failure, account):
    """
    Process a newly ingested failure through the recovery engine (Autopilot mode).
    Supervised accounts skip this — actions queued for review in Story 3.4.
    """
    from core.engine.processor import get_recovery_action
    from core.services.recovery import execute_recovery_action

    decision = get_recovery_action(
        failure.decline_code,
        payment_method_country=failure.payment_method_country,
    )

    # Log geo-compliance override if applicable
    if decision.geo_blocked:
        write_audit_event(
            subscriber=str(failure.subscriber.id),
            actor="engine",
            action="geo_compliance_override",
            outcome="success",
            metadata={
                "decline_code": failure.decline_code,
                "original_action": decision.rule["action"],
                "overridden_to": decision.action,
                "payment_method_country": failure.payment_method_country,
                "failure_id": str(failure.id),
            },
            account=account,
        )

    execute_recovery_action(failure, decision, account)


# Stripe subscription statuses that indicate recovery should stop
CANCELLATION_STATUSES = {"canceled", "unpaid", "paused"}


def _check_subscription_cancellations(account, access_token):
    """
    Check active subscribers for cancelled/paused Stripe subscriptions.
    Transitions them to passive_churn and stops pending retries (AC7).
    """
    from core.engine.state_machine import STATUS_ACTIVE
    from core.models.subscriber import Subscriber, SubscriberFailure

    active_subscribers = Subscriber.objects.for_account(account.id).filter(status=STATUS_ACTIVE)

    for subscriber in active_subscribers:
        try:
            subscriptions = stripe.Subscription.list(
                customer=subscriber.stripe_customer_id,
                api_key=access_token,
                limit=10,
            )

            for sub in subscriptions.auto_paging_iter():
                cancel_reason = None

                if sub.status in CANCELLATION_STATUSES:
                    cancel_reason = sub.status
                elif getattr(sub, "cancel_at_period_end", False):
                    cancel_reason = "cancel_at_period_end"

                if cancel_reason:
                    subscriber.mark_passive_churn()
                    subscriber.save()

                    # Stop pending retries
                    SubscriberFailure.objects.for_account(account.id).filter(
                        subscriber=subscriber,
                        next_retry_at__isnull=False,
                    ).update(next_retry_at=None)

                    write_audit_event(
                        subscriber=str(subscriber.id),
                        actor="engine",
                        action="subscription_cancellation_detected",
                        outcome="success",
                        metadata={
                            "stripe_subscription_id": sub.id,
                            "reason": cancel_reason,
                        },
                        account=account,
                    )
                    break  # One cancellation is enough

        except stripe.StripeError as exc:
            logger.warning(
                "Failed to check subscriptions for subscriber %s: %s",
                subscriber.id, str(exc),
            )


def _detect_card_updates(account, access_token):
    """
    Detect payment method updates for active subscribers and trigger immediate retries.
    FR47: Card update triggers immediate retry, bypassing payday-aware schedule.
    """
    from core.engine.state_machine import STATUS_ACTIVE
    from core.models.subscriber import Subscriber, SubscriberFailure
    from core.tasks.retry import execute_retry

    active_subscribers = (
        Subscriber.objects
        .for_account(account.id)
        .filter(status=STATUS_ACTIVE)
    )

    for subscriber in active_subscribers:
        # Only check subscribers with pending failures
        has_pending = SubscriberFailure.objects.for_account(account.id).filter(
            subscriber=subscriber,
        ).exclude(
            next_retry_at__isnull=True, retry_count__gte=3,
        ).exists()

        if not has_pending:
            continue

        try:
            fingerprint = _get_customer_fingerprint(subscriber, access_token)
            if fingerprint is None:
                continue

            old_fingerprint = subscriber.last_payment_method_fingerprint

            # Always update fingerprint
            if fingerprint != old_fingerprint:
                subscriber.last_payment_method_fingerprint = fingerprint
                subscriber.save(update_fields=["last_payment_method_fingerprint"])

            # Only trigger retry if fingerprint actually changed (not first detection)
            if old_fingerprint is not None and fingerprint != old_fingerprint:
                _queue_immediate_retry(subscriber, account)

        except stripe.StripeError as exc:
            logger.warning(
                "Failed to check card update for subscriber %s: %s",
                subscriber.id, str(exc),
            )


def _get_customer_fingerprint(subscriber, access_token):
    """
    Retrieve the payment method fingerprint for a subscriber's default payment method.
    Returns None if no default payment method or no card fingerprint available.
    """
    customer = stripe.Customer.retrieve(
        subscriber.stripe_customer_id,
        api_key=access_token,
        expand=["invoice_settings.default_payment_method"],
    )

    pm = getattr(customer, "invoice_settings", None)
    if pm is None:
        return None

    default_pm = getattr(pm, "default_payment_method", None)
    if default_pm is None or not hasattr(default_pm, "card"):
        return None

    card = getattr(default_pm, "card", None)
    if card is None:
        return None

    return getattr(card, "fingerprint", None)


def _queue_immediate_retry(subscriber, account):
    """
    Queue an immediate retry for the subscriber's most recent active failure.
    Autopilot: dispatches execute_retry immediately.
    Supervised: creates a PendingAction for client review.
    """
    from core.models.subscriber import SubscriberFailure
    from core.tasks.retry import execute_retry

    if subscriber.excluded_from_automation:
        return

    failure = (
        SubscriberFailure.objects
        .for_account(account.id)
        .filter(subscriber=subscriber)
        .order_by("-failure_created_at")
        .first()
    )

    if failure is None:
        return

    if account.engine_mode == "supervised":
        _process_supervised_queue(failure, account)
        return

    now = timezone.now()
    failure.next_retry_at = now
    failure.save(update_fields=["next_retry_at"])

    # Dispatch immediately for zero-delay retry
    execute_retry.delay(failure.id)

    write_audit_event(
        subscriber=str(subscriber.id),
        actor="engine",
        action="retry_queued",
        outcome="success",
        metadata={
            "trigger": "card_update_detected",
            "failure_id": str(failure.id),
            "payment_intent_id": failure.payment_intent_id,
        },
        account=account,
    )
