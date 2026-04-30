"""DPA versioning + gate utilities.

Centralizes the canonical DPA version identifier and the gate helper
used by every email-dispatch endpoint. The version string is bumped
by hand when the DPA legal text changes — accounts that signed an
older version remain bound by what they signed (per the carry-forward
rule, Story 3.1 v1 AC3).
"""
from rest_framework import status
from rest_framework.response import Response

# Bump this string when the DPA legal copy changes (NOT the rendering).
# Format: "vN.M-YYYY-MM-DD" — the date is the publish date, not the
# build date. The string IS the version hash for v1 — we don't hash
# the DPA text at runtime because the text lives in the frontend
# (frontend/src/app/(dashboard)/activate/page.tsx) and is reviewed
# by hand on every legal change.
CURRENT_DPA_VERSION = "v1.0-2026-04-29"

# Sentinel value for accounts that signed the pre-2026-04-29 DPA
# (the v0 engine-mode-coupled DPA). Carry-forward per AC3.
LEGACY_V0_DPA_VERSION = "v0-legacy"


def require_dpa_accepted(account):
    """Returns a 403 DRF Response if the account has not signed the DPA.
    Returns None when DPA is accepted (caller continues normally).

    Use at the TOP of every send-email endpoint (per-row + batch)
    BEFORE any tenant scoping or business logic — the gate must be
    the first thing checked so a malformed payload still returns
    DPA_REQUIRED rather than VALIDATION_ERROR.
    """
    if account.dpa_accepted:
        return None
    return Response(
        {"error": {
            "code": "DPA_REQUIRED",
            "message": "Sign the DPA to enable email sends.",
            "field": None,
        }},
        status=status.HTTP_403_FORBIDDEN,
    )
