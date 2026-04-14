"""
Shared failure ingestion logic used by both the retroactive scanner and the hourly poller.
Extracts, classifies, and persists a single failed payment intent.
"""
from datetime import datetime, timezone

from core.engine.rules import get_rule
from core.models.subscriber import Subscriber, SubscriberFailure


def ingest_failed_payment(account, payment_intent) -> tuple[Subscriber, SubscriberFailure, bool]:
    """
    Process a single failed payment intent into Subscriber + SubscriberFailure records.
    Returns (subscriber, failure, created) — `created` is False if already existed (idempotent).
    """
    # Extract decline code — may be None for non-card failures
    decline_code = None
    if payment_intent.last_payment_error:
        decline_code = payment_intent.last_payment_error.decline_code
    if not decline_code:
        decline_code = "_default"

    # Extract customer info
    stripe_customer_id = payment_intent.customer or f"unknown_{payment_intent.id}"
    email = ""
    payment_method_country = None

    charges = getattr(payment_intent, "charges", None)
    if charges and charges.data:
        charge = charges.data[0]
        billing_email = getattr(charge.billing_details, "email", None) if charge.billing_details else None
        if billing_email:
            email = billing_email

        pm_details = getattr(charge, "payment_method_details", None)
        if pm_details:
            card = getattr(pm_details, "card", None)
            if card:
                payment_method_country = getattr(card, "country", None)

    # Extract card fingerprint for card-update detection baseline
    card_fingerprint = None
    if charges and charges.data:
        charge = charges.data[0]
        pm_details_fp = getattr(charge, "payment_method_details", None)
        if pm_details_fp:
            card_fp = getattr(pm_details_fp, "card", None)
            if card_fp:
                card_fingerprint = getattr(card_fp, "fingerprint", None)

    # Classify via decline rules
    rule = get_rule(decline_code)
    classified_action = rule["action"]

    # Upsert Subscriber
    subscriber, _ = Subscriber.objects.get_or_create(
        stripe_customer_id=stripe_customer_id,
        account=account,
        defaults={"email": email},
    )
    # Update email if we have one and subscriber didn't
    update_fields = []
    if email and not subscriber.email:
        subscriber.email = email
        update_fields.append("email")
    # Populate initial fingerprint if not set (establishes baseline)
    if card_fingerprint and not subscriber.last_payment_method_fingerprint:
        subscriber.last_payment_method_fingerprint = card_fingerprint
        update_fields.append("last_payment_method_fingerprint")
    if update_fields:
        subscriber.save(update_fields=update_fields)

    # Parse Stripe timestamp
    failure_created_at = datetime.fromtimestamp(payment_intent.created, tz=timezone.utc)

    # Upsert SubscriberFailure (idempotent on payment_intent_id)
    failure, created = SubscriberFailure.objects.get_or_create(
        payment_intent_id=payment_intent.id,
        defaults={
            "subscriber": subscriber,
            "account": account,
            "decline_code": decline_code,
            "amount_cents": payment_intent.amount,
            "payment_method_country": payment_method_country,
            "failure_created_at": failure_created_at,
            "classified_action": classified_action,
        },
    )

    return subscriber, failure, created
