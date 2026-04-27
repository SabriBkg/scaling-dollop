"""Stateless signed opt-out tokens (Story 4.4).

`subscriber_email` is canonicalized (strip + lower) before signing so the
gate-4 lookup at `notifications.py` (which uses `subscriber_email__iexact=
subscriber.email.strip()`) matches the signed payload exactly.

Tokens never expire — opt-out links are a contractual / transactional surface
under GDPR (FR26). Do not introduce a `max_age`.
"""
from django.conf import settings
from django.core.signing import TimestampSigner

# Module-private salt scopes the signing key to this flow only. A token signed
# elsewhere with the project SECRET_KEY (e.g. password-reset in 4.5) cannot be
# replayed against this endpoint.
_SALT = "safenet.notifications.optout"


def build_optout_token(subscriber_email: str, account_id) -> str:
    """Sign a stateless opt-out token.

    The `(email, account_id)` payload is the only PII in the token —
    deliberately minimal because signed tokens are public-by-design.
    """
    signer = TimestampSigner(salt=_SALT)
    payload = {
        "email": (subscriber_email or "").strip().lower(),
        "account_id": int(account_id),
    }
    return signer.sign_object(payload)


def decode_optout_token(token: str) -> dict:
    """Decode a signed opt-out token. Raises `BadSignature` on tamper.

    `max_age=None` is intentional: opt-out links must work indefinitely.
    """
    signer = TimestampSigner(salt=_SALT)
    return signer.unsign_object(token, max_age=None)


def build_optout_url(subscriber_email: str, account_id) -> str:
    """Build the fully qualified opt-out URL embedded in notification emails."""
    token = build_optout_token(subscriber_email, account_id)
    base = settings.SAFENET_BASE_URL.rstrip("/")
    return f"{base}/optout/{token}/"
