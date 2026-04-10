"""
Stripe Connect OAuth views.

Flow:
  POST /api/v1/stripe/connect/    → returns {data: {oauth_url: "...", state: "..."}}
  POST /api/v1/stripe/callback/   → receives {code, state}, creates account, returns JWT tokens

The frontend:
  1. Calls /stripe/connect/ → gets oauth_url
  2. Redirects browser to oauth_url (Stripe Express Connect)
  3. Stripe redirects to NEXT_PUBLIC_BASE_URL/register/callback?code=xxx&state=xxx
  4. Callback page calls /stripe/callback/ with {code, state}
  5. Gets back {access, refresh, account_id} → stores cookies → redirects to /dashboard
"""
import secrets
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import transaction
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

env = environ.Env()


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

    # Validate CSRF state token
    state_key = f"stripe_oauth_state:{state}"
    if not cache.get(state_key):
        return Response(
            {"error": {"code": "INVALID_STATE", "message": "OAuth state is invalid or expired. Please try again.", "field": None}},
            status=status.HTTP_400_BAD_REQUEST,
        )
    cache.delete(state_key)  # One-time use

    # Exchange code for Stripe access token
    try:
        stripe_data = exchange_oauth_code(code)
    except Exception:
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
    try:
        with transaction.atomic():
            # Idempotency check: StripeConnection already exists for this stripe_user_id
            existing_connection = StripeConnection.objects.filter(
                stripe_user_id=stripe_user_id
            ).select_related("account__owner").first()

            if existing_connection:
                # Account already exists — issue new JWT tokens (re-login)
                user = existing_connection.account.owner
                account = existing_connection.account
            else:
                # New account: create User (signal auto-creates Account) + StripeConnection
                user, created = User.objects.get_or_create(
                    email=email,
                    defaults={
                        "username": email,
                        "is_staff": False,  # CRITICAL: Never True for client accounts (NFR-S4)
                        "is_superuser": False,
                    },
                )

                # Signal auto-creates Account on User creation.
                # Update it with tier and trial_ends_at for the 30-day Mid-tier trial (AC3).
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

    except Exception as exc:
        import logging
        logging.getLogger("django").exception("Stripe callback failed: %s", exc)
        return Response(
            {"error": {"code": "ACCOUNT_CREATION_FAILED", "message": "Failed to create your account. Please try again.", "field": None}},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # Issue JWT tokens
    refresh = RefreshToken.for_user(user)
    refresh["account_id"] = account.id  # Match SafeNetTokenObtainPairSerializer

    return Response({
        "data": {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "account_id": account.id,
        }
    })
