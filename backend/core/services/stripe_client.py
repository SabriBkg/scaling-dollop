"""
Stripe Express Connect OAuth helpers.
Wraps the Stripe OAuth flow — token exchange only.
Zero business logic here — just the HTTP exchange.
"""
import stripe
import environ

env = environ.Env()


def get_stripe_secret_key() -> str:
    return env("STRIPE_SECRET_KEY")


def get_oauth_url(redirect_uri: str, state: str) -> str:
    """
    Generate the Stripe Express Connect OAuth URL.
    'state' is a CSRF token — must be validated in the callback.
    """
    client_id = env("STRIPE_CLIENT_ID")
    stripe.api_key = get_stripe_secret_key()

    return (
        f"https://connect.stripe.com/oauth/authorize"
        f"?response_type=code"
        f"&client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&scope=read_write"
        f"&state={state}"
    )


def exchange_oauth_code(code: str) -> dict:
    """
    Exchange a Stripe OAuth authorization code for an access token.

    Returns dict with keys: access_token, stripe_user_id, livemode, etc.
    Raises stripe.oauth_error.OAuthError on failure (e.g. invalid code).
    """
    stripe.api_key = get_stripe_secret_key()
    response = stripe.OAuth.token(
        grant_type="authorization_code",
        code=code,
    )
    return {
        "access_token": response.access_token,
        "stripe_user_id": response.stripe_user_id,
        "livemode": response.livemode,
    }


def get_stripe_account_email(stripe_user_id: str, access_token: str) -> str | None:
    """
    Fetch the email from the connected Stripe Express account.
    Returns None if not available (email may be None for Express accounts).
    """
    stripe.api_key = access_token
    try:
        account = stripe.Account.retrieve(stripe_user_id)
        return account.email or getattr(account.business_profile, "support_email", None)
    except Exception:
        return None
