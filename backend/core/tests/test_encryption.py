import pytest
from unittest.mock import patch
from cryptography.fernet import Fernet


@pytest.fixture
def fernet_key():
    return Fernet.generate_key().decode()


def test_encrypt_decrypt_round_trip(fernet_key):
    with patch.dict("os.environ", {"STRIPE_TOKEN_KEY": fernet_key}):
        from core.services import encryption
        encryption._cipher = None  # reset cached cipher

        raw_token = "tok_live_abc123xyz"
        ciphertext = encryption.encrypt_token(raw_token)
        assert ciphertext != raw_token
        assert encryption.decrypt_token(ciphertext) == raw_token


def test_ciphertext_is_unique_per_call(fernet_key):
    """Fernet uses random IVs — same input produces different ciphertext each time."""
    with patch.dict("os.environ", {"STRIPE_TOKEN_KEY": fernet_key}):
        from core.services import encryption
        encryption._cipher = None

        t1 = encryption.encrypt_token("tok_live_abc")
        t2 = encryption.encrypt_token("tok_live_abc")
        assert t1 != t2  # random IV — both decrypt correctly
        assert encryption.decrypt_token(t1) == "tok_live_abc"
        assert encryption.decrypt_token(t2) == "tok_live_abc"


def test_stripeconnection_stores_ciphertext(db, account, fernet_key):
    with patch.dict("os.environ", {"STRIPE_TOKEN_KEY": fernet_key}):
        from core.services import encryption
        encryption._cipher = None

        from core.models.account import StripeConnection
        conn = StripeConnection(account=account, stripe_user_id="acct_test")
        conn.access_token = "tok_live_secret"
        conn.save()

        # Reload from DB — stored value is ciphertext, not raw token
        refreshed = StripeConnection.objects.get(pk=conn.pk)
        assert refreshed._encrypted_access_token != "tok_live_secret"
        assert refreshed.access_token == "tok_live_secret"


def test_raw_token_not_stored_in_db(db, account, fernet_key):
    """Verify DB breach alone cannot expose raw token."""
    with patch.dict("os.environ", {"STRIPE_TOKEN_KEY": fernet_key}):
        from core.services import encryption
        encryption._cipher = None

        from core.models.account import StripeConnection
        conn = StripeConnection(account=account, stripe_user_id="acct_breach_test")
        conn.access_token = "sk_live_verysecret"
        conn.save()

        # Direct DB value — should never be the raw token
        raw_db_value = StripeConnection.objects.values_list("_encrypted_access_token", flat=True).get(pk=conn.pk)
        assert raw_db_value != "sk_live_verysecret"
        assert len(raw_db_value) > 20  # ciphertext is longer than the raw token
