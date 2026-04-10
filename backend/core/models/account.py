from django.contrib.auth.models import User
from django.db import models

from core.services.encryption import encrypt_token, decrypt_token


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
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "core_account"

    def __str__(self):
        return f"Account({self.owner.email})"


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
    stripe_user_id = models.CharField(max_length=255)  # Stripe account ID (e.g. acct_xxx)
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
