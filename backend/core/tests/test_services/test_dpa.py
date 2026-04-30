"""Tests for the DPA gate helper at core/services/dpa.py."""
import pytest

from core.services.dpa import (
    CURRENT_DPA_VERSION,
    LEGACY_V0_DPA_VERSION,
    require_dpa_accepted,
)


@pytest.mark.django_db
class TestRequireDpaAccepted:
    def test_returns_403_when_unsigned(self, account):
        # No dpa_accepted_at set on the auto-created account fixture.
        response = require_dpa_accepted(account)

        assert response is not None
        assert response.status_code == 403
        assert response.data == {
            "error": {
                "code": "DPA_REQUIRED",
                "message": "Sign the DPA to enable email sends.",
                "field": None,
            }
        }

    def test_returns_none_when_signed_v1(self, account):
        from django.utils import timezone
        account.dpa_accepted_at = timezone.now()
        account.dpa_version = CURRENT_DPA_VERSION
        account.save()

        assert require_dpa_accepted(account) is None

    def test_returns_none_when_signed_v0_legacy(self, account):
        from django.utils import timezone
        account.dpa_accepted_at = timezone.now()
        account.dpa_version = LEGACY_V0_DPA_VERSION
        account.save()

        assert require_dpa_accepted(account) is None
