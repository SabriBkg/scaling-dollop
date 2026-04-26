"""Tests for the Account model — focused on fields specific to this story."""
import pytest
from django.core.exceptions import ValidationError

from core.models.account import (
    Account,
    DEFAULT_TONE,
    TONE_CHOICES,
    TONE_FRIENDLY,
    TONE_MINIMAL,
    TONE_PROFESSIONAL,
)


@pytest.mark.django_db
class TestAccountNotificationTone:
    def test_default_is_professional(self, account):
        assert account.notification_tone == TONE_PROFESSIONAL
        assert DEFAULT_TONE == TONE_PROFESSIONAL

    def test_choices_constant_lists_three_tones(self):
        values = {value for value, _label in TONE_CHOICES}
        assert values == {TONE_PROFESSIONAL, TONE_FRIENDLY, TONE_MINIMAL}

    @pytest.mark.parametrize("tone", [TONE_PROFESSIONAL, TONE_FRIENDLY, TONE_MINIMAL])
    def test_full_clean_accepts_valid_tone(self, account, tone):
        account.notification_tone = tone
        account.full_clean()  # raises if invalid

    def test_full_clean_rejects_invalid_tone(self, account):
        account.notification_tone = "shouting"
        with pytest.raises(ValidationError):
            account.full_clean()

    def test_persists_across_save_and_reload(self, account):
        account.notification_tone = TONE_FRIENDLY
        account.save(update_fields=["notification_tone"])
        reloaded = Account.objects.get(pk=account.pk)
        assert reloaded.notification_tone == TONE_FRIENDLY
