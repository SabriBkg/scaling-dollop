"""Throttle classes for the password reset endpoints (Story 4.5).

`PasswordResetRequestThrottle` keys by request-body email (sha256 hashed)
so the rate limit applies per-email, not per-IP. Falls back to IP keying
when email is missing/blank (defense against empty-body abuse).

`PasswordResetConfirmThrottle` keys by IP at the existing `auth` scope —
UID is attacker-controlled, IP is not.
"""
import hashlib
import unicodedata

from rest_framework.throttling import SimpleRateThrottle


def _normalize_email(raw) -> str:
    if not isinstance(raw, str):
        return ""
    return unicodedata.normalize("NFKC", raw).strip().lower()


class PasswordResetRequestThrottle(SimpleRateThrottle):
    scope = "password_reset"

    def get_cache_key(self, request, view):
        email = _normalize_email(request.data.get("email"))
        if email:
            ident = hashlib.sha256(email.encode()).hexdigest()[:32]
            return f"throttle_password_reset_{ident}"
        ip = self.get_ident(request)
        return f"throttle_password_reset_anon_{ip}"


class PasswordResetConfirmThrottle(SimpleRateThrottle):
    scope = "auth"  # reuse the existing 5/min auth scope

    def get_cache_key(self, request, view):
        return f"throttle_password_reset_confirm_{self.get_ident(request)}"
