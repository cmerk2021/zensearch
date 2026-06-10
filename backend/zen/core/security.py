"""Security primitives: password hashing, tokens, and secret encryption.

Passwords use argon2id (OWASP recommendation). Session tokens are opaque
256-bit values stored only as SHA-256 hashes (ADR-0006). Instance-level
secrets (provider/AI API keys) are encrypted at rest with a Fernet key
derived from ``ZEN_SECRET_KEY`` (ADR-0003).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError
from cryptography.fernet import Fernet, InvalidToken

_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)

SESSION_TOKEN_BYTES = 32
CSRF_TOKEN_BYTES = 32


# --- Passwords --------------------------------------------------------------


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        _hasher.verify(password_hash, password)
        return True
    except (VerifyMismatchError, VerificationError, ValueError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    try:
        return _hasher.check_needs_rehash(password_hash)
    except Exception:
        return True


def validate_password_strength(password: str) -> list[str]:
    """Return a list of human-readable problems; empty list means acceptable."""
    problems: list[str] = []
    if len(password) < 10:
        problems.append("Password must be at least 10 characters long.")
    if len(password) > 256:
        problems.append("Password must be at most 256 characters long.")
    if password.lower() == password and password.upper() == password:
        # All digits/symbols — fine, length rule covers entropy; skip.
        pass
    if password.lower() in _COMMON_PASSWORDS:
        problems.append("Password is too common.")
    return problems


_COMMON_PASSWORDS = {
    "password123", "1234567890", "qwertyuiop", "administrator",
    "letmein123", "password1!", "zenzenzenzen",
}


# --- Opaque tokens -----------------------------------------------------------


def generate_token(nbytes: int = SESSION_TOKEN_BYTES) -> str:
    return secrets.token_urlsafe(nbytes)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def constant_time_compare(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


# --- Secret encryption (instance settings layer) -----------------------------


def _fernet(secret_key: str) -> Fernet:
    digest = hashlib.sha256(f"zen.secrets.v1:{secret_key}".encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


SECRET_PREFIX = "enc:v1:"


def encrypt_secret(plaintext: str, secret_key: str) -> str:
    if not plaintext:
        return ""
    token = _fernet(secret_key).encrypt(plaintext.encode("utf-8")).decode("ascii")
    return f"{SECRET_PREFIX}{token}"


def decrypt_secret(ciphertext: str, secret_key: str) -> str:
    if not ciphertext:
        return ""
    if not ciphertext.startswith(SECRET_PREFIX):
        # Legacy/plaintext value tolerated for imports; callers re-encrypt on save.
        return ciphertext
    try:
        raw = ciphertext[len(SECRET_PREFIX):].encode("ascii")
        return _fernet(secret_key).decrypt(raw).decode("utf-8")
    except (InvalidToken, ValueError) as exc:
        raise ValueError("Failed to decrypt secret: wrong ZEN_SECRET_KEY?") from exc


def redact_secret(value: str) -> str:
    """Mask a secret for display: keep at most last 4 characters."""
    if not value:
        return ""
    tail = value[-4:] if len(value) > 8 else ""
    return f"••••••••{tail}"
