"""
Stripe Connect OAuth helpers.
Wraps the Stripe OAuth flow — token exchange only.
Zero business logic here — just the HTTP exchange.
"""
import stripe
import environ
from urllib.parse import urlencode

env = environ.Env()


def get_stripe_secret_key() -> str:
    return env("STRIPE_SECRET_KEY")


def get_oauth_url(redirect_uri: str, state: str) -> str:
    """
    Generate the Stripe Connect OAuth URL.
    'state' is a CSRF token — must be validated in the callback.
    """
    client_id = env("STRIPE_CLIENT_ID")
    params = urlencode({
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": "read_write",
        "state": state,
    })
    return f"https://connect.stripe.com/oauth/authorize?{params}"


def exchange_oauth_code(code: str) -> dict:
    """
    Exchange a Stripe OAuth authorization code for an access token.

    Returns dict with keys: access_token, stripe_user_id, livemode, etc.
    Raises stripe.error.StripeError on failure (e.g. invalid code).
    """
    response = stripe.OAuth.token(
        grant_type="authorization_code",
        code=code,
        api_key=get_stripe_secret_key(),
    )
    return {
        "access_token": response.access_token,
        "stripe_user_id": response.stripe_user_id,
        "livemode": response.livemode,
    }


def get_stripe_account_email(stripe_user_id: str, access_token: str) -> str | None:
    """
    Fetch the email from the connected Stripe account.
    Returns None if not available (email may be None for Express accounts).
    """
    try:
        account = stripe.Account.retrieve(stripe_user_id, api_key=access_token)
        return account.email or getattr(account.business_profile, "support_email", None)
    except Exception:
        return None
