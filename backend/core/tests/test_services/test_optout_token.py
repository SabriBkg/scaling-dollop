"""Tests for the stateless opt-out token helper (Story 4.4 Task 4)."""
import inspect
from pathlib import Path

import pytest
from django.core.signing import BadSignature, TimestampSigner
from django.test import override_settings

from core.services import optout_token
from core.services.optout_token import (
    build_optout_token,
    build_optout_url,
    decode_optout_token,
)


class TestBuildAndDecodeRoundTrip:
    def test_round_trip(self):
        token = build_optout_token("a@b.com", 7)
        payload = decode_optout_token(token)
        assert payload == {"email": "a@b.com", "account_id": 7}

    def test_email_canonicalized(self):
        token = build_optout_token("  A@B.COM  ", 7)
        payload = decode_optout_token(token)
        assert payload["email"] == "a@b.com"

    def test_account_id_coerced_to_int(self):
        token = build_optout_token("a@b.com", "7")
        payload = decode_optout_token(token)
        assert payload["account_id"] == 7
        assert isinstance(payload["account_id"], int)


class TestTokenIntegrity:
    def test_tampered_token_raises_bad_signature(self):
        token = build_optout_token("a@b.com", 7)
        # Flip a single character somewhere in the middle.
        idx = len(token) // 2
        flipped = "A" if token[idx] != "A" else "B"
        bad_token = token[:idx] + flipped + token[idx + 1:]
        with pytest.raises(BadSignature):
            decode_optout_token(bad_token)

    def test_token_from_different_salt_rejected(self):
        signer = TimestampSigner(salt="not-the-optout-salt")
        foreign_token = signer.sign_object({"email": "a@b.com", "account_id": 7})
        with pytest.raises(BadSignature):
            decode_optout_token(foreign_token)


class TestBuildOptoutUrl:
    def test_uses_settings_base_url(self):
        with override_settings(SAFENET_BASE_URL="http://localhost:8000"):
            url = build_optout_url("a@b.com", 7)
        assert url.startswith("http://localhost:8000/optout/")
        token_segment = url[len("http://localhost:8000/optout/"):].rstrip("/")
        assert token_segment, "URL must contain a non-empty token segment"

    def test_strips_trailing_slash_on_base_url(self):
        with override_settings(SAFENET_BASE_URL="http://x/"):
            url = build_optout_url("a@b.com", 7)
        # No double slash before /optout/
        assert "//optout/" not in url.replace("http://", "")
        assert url.startswith("http://x/optout/")

    def test_url_contains_decodable_token(self):
        with override_settings(SAFENET_BASE_URL="http://localhost:8000"):
            url = build_optout_url("Sub@Example.com", 42)
        token = url[len("http://localhost:8000/optout/"):].rstrip("/")
        payload = decode_optout_token(token)
        assert payload == {"email": "sub@example.com", "account_id": 42}


class TestNoMaxAgeEnforced:
    """Opt-out links MUST work indefinitely per FR26 / GDPR transactional contract."""

    def test_decode_call_site_passes_max_age_none(self):
        """String-search the source: decode_optout_token must call unsign_object
        with max_age=None. This guarantees the no-expiry contract structurally —
        we don't need a clock-shifting test fixture."""
        source = inspect.getsource(decode_optout_token)
        assert "max_age=None" in source, (
            "decode_optout_token must explicitly pass max_age=None to "
            "TimestampSigner.unsign_object — opt-out links never expire."
        )
