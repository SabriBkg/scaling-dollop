"""
Stripe Billing views: webhook handler and checkout session creation.
"""
import logging

import stripe
import environ
from django.core.cache import cache
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.models.account import Account, TIER_FREE
from core.services.audit import write_audit_event
from core.services.tier import upgrade_to_mid

env = environ.Env()
logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def stripe_billing_webhook(request):
    """
    Handle Stripe Billing webhooks (checkout.session.completed, customer.subscription.deleted).
    Exempt from JWT auth and CSRF — verified via Stripe signature.
    """
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, env("STRIPE_WEBHOOK_SECRET", default="")
        )
    except stripe.StripeError:
        return HttpResponse("Invalid signature", status=400)

    event_type = event["type"]

    if event_type == "checkout.session.completed":
        session = event["data"]["object"]
        account_id = session.get("client_reference_id")
        if account_id:
            try:
                account = Account.objects.get(id=account_id)
                upgrade_to_mid(account)
                # Invalidate dashboard cache so new tier is reflected immediately
                cache.delete(f"dashboard_summary_{account.id}")
                write_audit_event(
                    subscriber=None,
                    actor="client",
                    action="subscription_upgraded",
                    outcome="success",
                    account=account,
                    metadata={"from_tier": TIER_FREE, "to_tier": "mid"},
                )
                logger.info("Account %s upgraded to Mid via checkout", account_id)
            except Account.DoesNotExist:
                logger.warning("Checkout completed for unknown account %s", account_id)

    elif event_type == "customer.subscription.deleted":
        subscription = event["data"]["object"]
        account_id = subscription.get("metadata", {}).get("account_id")
        if account_id:
            try:
                account = Account.objects.get(id=account_id)
                account.tier = TIER_FREE
                account.save(update_fields=["tier"])
                cache.delete(f"dashboard_summary_{account.id}")
                write_audit_event(
                    subscriber=None,
                    actor="engine",
                    action="subscription_cancelled",
                    outcome="success",
                    account=account,
                )
                logger.info("Account %s downgraded to Free (subscription deleted)", account_id)
            except Account.DoesNotExist:
                logger.warning("Subscription deleted for unknown account %s", account_id)

    return HttpResponse("OK", status=200)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_checkout_session(request):
    """
    Create a Stripe Checkout Session for upgrading to Mid tier.
    Returns the checkout URL for frontend redirect.
    """
    try:
        account = request.user.account
    except request.user.__class__.account.RelatedObjectDoesNotExist:
        return Response(
            {"error": {"code": "NO_ACCOUNT", "message": "No account found.", "field": None}},
            status=status.HTTP_404_NOT_FOUND,
        )

    try:
        frontend_base = env("NEXT_PUBLIC_BASE_URL", default="http://localhost:3000")
        session = stripe.checkout.Session.create(
            mode="subscription",
            payment_method_types=["card"],
            line_items=[{
                "price": env("STRIPE_MID_TIER_PRICE_ID", default=""),
                "quantity": 1,
            }],
            client_reference_id=str(account.id),
            success_url=f"{frontend_base}/dashboard?upgrade=success",
            cancel_url=f"{frontend_base}/dashboard?upgrade=cancelled",
            metadata={"account_id": str(account.id)},
        )

        return Response({"data": {"checkout_url": session.url}})

    except stripe.StripeError as e:
        logger.error("Failed to create checkout session: %s", e)
        return Response(
            {"error": {"code": "CHECKOUT_FAILED", "message": "Failed to create checkout session.", "field": None}},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
