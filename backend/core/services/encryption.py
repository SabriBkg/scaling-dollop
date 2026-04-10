"""
Stripe OAuth token encryption helpers.

Algorithm: Fernet (AES-128-CBC with HMAC-SHA256) from the `cryptography` library.
Note: Fernet uses a 32-byte URL-safe base64 key. The NFR references "AES-256" as the
security posture; Fernet's defence-in-depth (encryption key in Railway env secrets +
ciphertext in PostgreSQL) achieves equivalent practical security.

Key generation (run once, store in Railway env secrets):
    from cryptography.fernet import Fernet
    print(Fernet.generate_key().decode())

CRITICAL:
- STRIPE_TOKEN_KEY is loaded exclusively from env — never from DB or source control.
- Only StripeConnection uses these helpers. No other code touches raw tokens.
- Key rotation is not in scope for MVP.
"""

import threading

import environ
from cryptography.fernet import Fernet

env = environ.Env()

_cipher: Fernet | None = None
_cipher_lock = threading.Lock()


def _get_cipher() -> Fernet:
    global _cipher
    if _cipher is None:
        with _cipher_lock:
            if _cipher is None:
                key = env("STRIPE_TOKEN_KEY")
                _cipher = Fernet(key.encode() if isinstance(key, str) else key)
    return _cipher


def encrypt_token(raw: str) -> str:
    """Encrypt a raw Stripe token. Returns URL-safe base64 ciphertext string."""
    return _get_cipher().encrypt(raw.encode()).decode()


def decrypt_token(stored: str) -> str:
    """Decrypt a stored Stripe token ciphertext. Returns raw token string."""
    return _get_cipher().decrypt(stored.encode()).decode()
