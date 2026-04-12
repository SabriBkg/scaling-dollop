"""
Stripe Connect OAuth views.

Flow:
  POST /api/v1/stripe/connect/    → returns {data: {oauth_url: "...", state: "..."}}
  POST /api/v1/stripe/callback/   → receives {code, state}, creates account, returns JWT tokens

The frontend:
  1. Calls /stripe/connect/ → gets oauth_url
  2. Redirects browser to oauth_url (Stripe Connect)
  3. Stripe redirects to NEXT_PUBLIC_BASE_URL/register/callback?code=xxx&state=xxx
  4. Callback page calls /stripe/callback/ with {code, state}
  5. Gets back {access, refresh, account_id} → stores cookies → redirects to /dashboard
"""
import logging
import secrets
from datetime import timedelta

import stripe
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.utils import timezone

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

import environ

from core.models.account import StripeConnection, TIER_MID
from core.services.audit import write_audit_event
from core.services.stripe_client import get_oauth_url, exchange_oauth_code, get_stripe_account_email
from core.tasks.scanner import scan_retroactive_failures

env = environ.Env()
logger = logging.getLogger("django")


@api_view(["POST"])
@permission_classes([AllowAny])
def initiate_stripe_connect(request):
    """
    Returns the Stripe Express Connect OAuth URL.
    Frontend redirects to this URL — does NOT redirect from the backend.

    Response: {data: {oauth_url: "https://connect.stripe.com/...", state: "abc123"}}
    """
    redirect_uri = env("STRIPE_REDIRECT_URI")
    state = secrets.token_urlsafe(32)

    # Store state in cache for CSRF validation in callback (10-minute expiry)
    cache.set(f"stripe_oauth_state:{state}", True, timeout=600)

    oauth_url = get_oauth_url(redirect_uri=redirect_uri, state=state)
    return Response({"data": {"oauth_url": oauth_url, "state": state}})


@api_view(["POST"])
@permission_classes([AllowAny])
def stripe_connect_callback(request):
    """
    Handles the OAuth callback from Stripe.
    Called by the FRONTEND (not Stripe directly) — the frontend page at /register/callback
    extracts the code+state from the URL and POSTs them here.

    Request body: {code: "ac_xxx", state: "abc123"}
    Response: {data: {access: "...", refresh: "...", account_id: 123}}
    Error: {error: {code: "...", message: "...", field: null}}
    """
    code = request.data.get("code")
    state = request.data.get("state")

    if not code or not state:
        return Response(
            {"error": {"code": "MISSING_PARAMS", "message": "Missing OAuth code or state parameter.", "field": None}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Validate CSRF state token (atomic check-and-delete)
    state_key = f"stripe_oauth_state:{state}"
    if not cache.delete(state_key):
        return Response(
            {"error": {"code": "INVALID_STATE", "message": "OAuth state is invalid or expired. Please try again.", "field": None}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Exchange code for Stripe access token
    try:
        stripe_data = exchange_oauth_code(code)
    except stripe.error.StripeError:
        return Response(
            {"error": {"code": "STRIPE_AUTH_FAILED", "message": "Stripe authorization failed. Please try connecting again.", "field": None}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    access_token = stripe_data["access_token"]
    stripe_user_id = stripe_data["stripe_user_id"]

    # Fetch email from Stripe account (for Django User creation)
    email = get_stripe_account_email(stripe_user_id, access_token)
    if not email:
        email = f"{stripe_user_id}@stripe-connect.safenet.local"

    # Atomic account creation — no partial records on failure (AC5)
    is_new_account = False
    try:
        with transaction.atomic():
            # Idempotency check: StripeConnection already exists for this stripe_user_id
            existing_connection = StripeConnection.objects.select_for_update().filter(
                stripe_user_id=stripe_user_id
            ).select_related("account__owner").first()

            if existing_connection:
                # Reconnection — update encrypted token and issue new JWT tokens
                existing_connection.access_token = access_token
                existing_connection.save(update_fields=["_encrypted_access_token"])
                user = existing_connection.account.owner
                account = existing_connection.account
            else:
                # Reject if a User with this email already exists (prevent account takeover)
                if User.objects.filter(email=email).exists():
                    return Response(
                        {"error": {"code": "EMAIL_EXISTS", "message": "An account with this email already exists. Please log in instead.", "field": None}},
                        status=status.HTTP_409_CONFLICT,
                    )

                # New account: create User (post_save signal auto-creates Account)
                user = User.objects.create_user(
                    username=email[:150],
                    email=email,
                    is_staff=False,  # CRITICAL: Never True for client accounts (NFR-S4)
                )

                # Signal creates Account — update with tier and trial (AC3)
                account = user.account
                account.tier = TIER_MID
                account.trial_ends_at = timezone.now() + timedelta(days=30)
                account.save(update_fields=["tier", "trial_ends_at"])

                # Store encrypted Stripe token
                connection = StripeConnection(account=account, stripe_user_id=stripe_user_id)
                connection.access_token = access_token  # Uses @property setter — encrypts via Fernet
                connection.save()

                # Audit log for account creation
                write_audit_event(
                    subscriber=None,
                    actor="client",
                    action="account_created",
                    outcome="success",
                    account=account,
                    metadata={"stripe_user_id": stripe_user_id, "tier": TIER_MID, "via": "stripe_oauth"},
                )

                is_new_account = True

    except Exception as exc:
        logger.exception("Stripe callback failed: %s", exc)
        return Response(
            {"error": {"code": "ACCOUNT_CREATION_FAILED", "message": "Failed to create your account. Please try again.", "field": None}},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # Queue retroactive scan AFTER transaction commits (ensures Account exists in DB)
    if is_new_account:
        scan_retroactive_failures.delay(account.id)

    # Issue JWT tokens
    refresh = RefreshToken.for_user(user)
    refresh["account_id"] = account.id  # Match SafeNetTokenObtainPairSerializer

    return Response({
        "data": {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "account_id": account.id,
            "is_new_account": is_new_account,
            "profile_complete": account.profile_complete,
        }
    })
