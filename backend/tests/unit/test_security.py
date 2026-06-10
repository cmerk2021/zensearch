"""Unit tests for security primitives."""

from zen.core.security import (
    constant_time_compare,
    decrypt_secret,
    encrypt_secret,
    generate_token,
    hash_password,
    hash_token,
    redact_secret,
    validate_password_strength,
    verify_password,
)

SECRET = "unit-test-secret-key"


def test_password_hash_roundtrip():
    digest = hash_password("correct horse battery staple")
    assert digest.startswith("$argon2id$")
    assert verify_password("correct horse battery staple", digest)
    assert not verify_password("wrong password", digest)


def test_verify_garbage_hash_is_false():
    assert not verify_password("anything", "not-a-hash")
    assert not verify_password("anything", "")


def test_password_strength():
    assert validate_password_strength("short") != []
    assert validate_password_strength("password123") != []
    assert validate_password_strength("a-perfectly-fine-passphrase") == []


def test_tokens_unique_and_hashed():
    t1, t2 = generate_token(), generate_token()
    assert t1 != t2
    assert len(hash_token(t1)) == 64
    assert hash_token(t1) != hash_token(t2)


def test_constant_time_compare():
    assert constant_time_compare("abc", "abc")
    assert not constant_time_compare("abc", "abd")


def test_secret_encryption_roundtrip():
    encrypted = encrypt_secret("my-api-key", SECRET)
    assert encrypted.startswith("enc:v1:")
    assert "my-api-key" not in encrypted
    assert decrypt_secret(encrypted, SECRET) == "my-api-key"


def test_secret_encryption_wrong_key_fails():
    encrypted = encrypt_secret("my-api-key", SECRET)
    import pytest

    with pytest.raises(ValueError):
        decrypt_secret(encrypted, "different-key")


def test_secret_empty_and_legacy_values():
    assert encrypt_secret("", SECRET) == ""
    assert decrypt_secret("", SECRET) == ""
    # Plaintext (legacy/import) values pass through.
    assert decrypt_secret("plain-value", SECRET) == "plain-value"


def test_redact_secret():
    assert redact_secret("") == ""
    assert redact_secret("short") == "••••••••"
    redacted = redact_secret("sk-1234567890abcdef")
    assert redacted.endswith("cdef")
    assert "1234567890" not in redacted
