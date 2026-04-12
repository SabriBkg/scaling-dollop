from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from core.services.encryption import encrypt_token, decrypt_token


TIER_FREE = "free"
TIER_MID = "mid"
TIER_PRO = "pro"

TIER_CHOICES = [
    (TIER_FREE, "Free"),
    (TIER_MID, "Mid"),
    (TIER_PRO, "Pro"),
]


class Account(models.Model):
    """
    The tenant entity. Every client has exactly one Account.

    Schema is intentionally forward-compatible: a future Membership join table
    (user_id, account_id, role) can be added without migrating this model (NFR-SC3).
    """
    owner = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="account",
    )
    tier = models.CharField(
        max_length=10,
        choices=TIER_CHOICES,
        default=TIER_MID,
    )
    trial_ends_at = models.DateTimeField(null=True, blank=True)
    company_name = models.CharField(max_length=200, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "core_account"

    def __str__(self):
        return f"Account({self.owner.email}, tier={self.tier})"

    @property
    def profile_complete(self) -> bool:
        """True if the owner has completed their profile (name + company + password)."""
        return bool(
            self.company_name
            and self.owner.first_name
            and self.owner.has_usable_password()
        )

    @property
    def is_on_trial(self) -> bool:
        """True if the account is in the 30-day Mid-tier trial period."""
        return self.tier == TIER_MID and self.trial_ends_at is not None and timezone.now() < self.trial_ends_at


class StripeConnection(models.Model):
    """
    Stores an encrypted Stripe OAuth token for a connected Account.
    One per Account. Raw token never stored — only ciphertext.

    Only this model uses encrypt/decrypt helpers. No other code in the codebase
    should touch raw Stripe tokens.
    """
    account = models.OneToOneField(
        Account,
        on_delete=models.CASCADE,
        related_name="stripe_connection",
    )
    _encrypted_access_token = models.TextField(db_column="encrypted_access_token")
    stripe_user_id = models.CharField(max_length=255, unique=True)  # Stripe account ID (e.g. acct_xxx)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "core_stripe_connection"

    @property
    def access_token(self) -> str:
        from cryptography.fernet import InvalidToken
        try:
            return decrypt_token(self._encrypted_access_token)
        except InvalidToken:
            raise ValueError(
                "Failed to decrypt Stripe token — key may have been rotated or ciphertext is corrupt."
            )

    @access_token.setter
    def access_token(self, raw_token: str):
        self._encrypted_access_token = encrypt_token(raw_token)
