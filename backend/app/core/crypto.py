"""Symmetric encryption for secrets at rest (security §7.4, NFR-2).

AI provider API keys entered via the UI are stored ENCRYPTED in the metadata DB,
never in plaintext and never echoed back to a client. We use Fernet (AES-128-CBC +
HMAC) with a key held in `AI_CONFIG_ENC_KEY` (a managed secret in production).

Fail-closed: if no encryption key is configured, encryption/decryption raises
rather than silently storing plaintext.
"""

from __future__ import annotations

from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


class SecretError(RuntimeError):
    """Raised when secret encryption is misconfigured or a token is invalid."""


@lru_cache
def _fernet() -> Fernet:
    key = settings.ai_config_enc_key
    if not key:
        raise SecretError(
            "AI_CONFIG_ENC_KEY is not set — cannot store/read encrypted secrets. "
            "Generate one with: python -c \"from cryptography.fernet import Fernet; "
            'print(Fernet.generate_key().decode())"'
        )
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except (ValueError, TypeError) as exc:
        raise SecretError("AI_CONFIG_ENC_KEY is not a valid Fernet key") from exc


def encrypt_secret(plaintext: str) -> str:
    """Encrypt a secret; returns URL-safe ciphertext for DB storage."""
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_secret(ciphertext: str) -> str:
    """Decrypt a stored secret. Raises SecretError on tampering/wrong key."""
    try:
        return _fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise SecretError("Could not decrypt secret (wrong key or corrupted value)") from exc


def encrypt_bytes(plaintext: bytes) -> bytes:
    """Encrypt raw bytes (e.g. an uploaded file) for DB storage at rest."""
    return _fernet().encrypt(plaintext)


def decrypt_bytes(ciphertext: bytes) -> bytes:
    """Decrypt bytes stored by `encrypt_bytes`. Raises SecretError on tampering."""
    try:
        return _fernet().decrypt(ciphertext)
    except InvalidToken as exc:
        raise SecretError("Could not decrypt file (wrong key or corrupted value)") from exc


def mask_secret(plaintext: str, *, keep: int = 4) -> str:
    """A non-reversible hint for display, e.g. 'sk-ant-…aB12'. Never the full key."""
    if not plaintext:
        return ""
    tail = plaintext[-keep:] if len(plaintext) > keep else ""
    return f"…{tail}"
