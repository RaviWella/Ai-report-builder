"""Decrypt MinHRM PHP launch payloads (AES-256-CBC, openssl_encrypt options=0)."""
from __future__ import annotations

import base64
import binascii
import json
from typing import Any

from app.core.config import settings
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

IV_LENGTH = 16


class HrisPayloadDecryptError(ValueError):
    """Invalid or tampered HRIS launch payload."""


def normalize_launch_payload(payload: str) -> str:
    """
    Normalize payload from URL query.

    Query parsing can turn base64 ``+`` into spaces; restore before decode.
    """
    p = payload.strip()
    if " " in p and "+" not in p:
        p = p.replace(" ", "+")
    return p


def normalize_launch_secret(secret: str) -> str:
    """
    Normalize HRIS_LAUNCH_SECRET_KEY from env / secrets managers.

    Docker, shell, and some UIs turn base64 ``+`` into spaces or ``%2B`` literals.
    """
    raw = secret.strip().strip('"').strip("'")
    if not raw:
        return raw
    if "%2B" in raw.upper() or "%2b" in raw:
        raw = raw.replace("%2B", "+").replace("%2b", "+")
    # Env mangling: shell/Docker often turns '+' into space when unquoted.
    if " " in raw and "+" not in raw:
        raw = raw.replace(" ", "+")
    return raw


def _b64_decode_secret_candidates(raw: str) -> list[bytes]:
    out: list[bytes] = []
    padded = raw + "=" * ((4 - len(raw) % 4) % 4)
    for value in (raw, padded):
        try:
            out.append(base64.b64decode(value, validate=False))
        except (binascii.Error, ValueError):
            pass
        try:
            out.append(base64.urlsafe_b64decode(value))
        except (binascii.Error, ValueError):
            pass
    return out


def _resolve_aes_key(secret: str) -> bytes:
    """
    Resolve AES-256 key the same way PHP should::

        base64_decode(self::$secretKey)  # 32 bytes for aes-256-cbc

    Also accepts a raw 32-byte UTF-8 secret (misconfigured env fallback).
    """
    raw = normalize_launch_secret(secret)
    if not raw:
        raise HrisPayloadDecryptError("HRIS launch secret is not configured")

    candidates: list[bytes] = _b64_decode_secret_candidates(raw)

    utf8 = raw.encode("utf-8")
    if len(utf8) == 32:
        candidates.append(utf8)

    for key in candidates:
        if len(key) == 32:
            return key

    raise HrisPayloadDecryptError(
        "Invalid HRIS launch secret encoding — HRIS_LAUNCH_SECRET_KEY must be the "
        "exact base64 string from PHP PythonPayroll::$secretKey (quote the value in "
        ".env if it contains '+'). Example: "
        'HRIS_LAUNCH_SECRET_KEY="hF8X...+2Tz..."'
    )


def _aes_cbc_decrypt(key: bytes, iv: bytes, ciphertext: bytes) -> bytes:
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    padded = decryptor.update(ciphertext) + decryptor.finalize()
    unpadder = padding.PKCS7(128).unpadder()
    return unpadder.update(padded) + unpadder.finalize()


def _inner_ciphertext_variants(inner: bytes) -> list[tuple[str, bytes]]:
    """PHP default (options=0): inner is base64 ASCII; rare: raw ciphertext after IV."""
    variants: list[tuple[str, bytes]] = []
    try:
        variants.append(("php_openssl_b64", base64.b64decode(inner, validate=False)))
    except (binascii.Error, ValueError):
        pass
    if len(inner) % 16 == 0:
        variants.append(("raw_ciphertext", inner))
    return variants


def decrypt_hris_payload(payload_b64: str, secret_key_b64: str) -> dict[str, Any]:
    """
    Match PHP::

        $iv = random 16 bytes
        $encrypted = openssl_encrypt(json_encode($data), 'aes-256-cbc', key, 0, $iv)
        return base64_encode($iv . $encrypted)

    With options=0, openssl_encrypt returns base64 ciphertext (ASCII), not raw bytes.
    """
    key = _resolve_aes_key(secret_key_b64)
    payload_b64 = normalize_launch_payload(payload_b64)

    try:
        blob = base64.b64decode(payload_b64, validate=False)
    except (binascii.Error, ValueError) as exc:
        raise HrisPayloadDecryptError("Payload is not valid base64") from exc

    if len(blob) <= IV_LENGTH:
        raise HrisPayloadDecryptError("Payload is too short")

    iv = blob[:IV_LENGTH]
    inner = blob[IV_LENGTH:]

    last_err: Exception | None = None
    for _label, ciphertext in _inner_ciphertext_variants(inner):
        try:
            plain = _aes_cbc_decrypt(key, iv, ciphertext)
        except (ValueError, KeyError) as exc:
            last_err = exc
            continue
        try:
            data = json.loads(plain.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HrisPayloadDecryptError("Payload is not valid JSON") from exc
        if not isinstance(data, dict):
            raise HrisPayloadDecryptError("Payload JSON must be an object")
        return data

    raise HrisPayloadDecryptError(
        "AES decrypt failed — set HRIS_LAUNCH_SECRET_KEY on the API to the exact "
        "base64 value of MinHRM PHP self::$secretKey (the string passed to base64_decode), "
        "then restart the API"
    ) from last_err


def list_hris_launch_secret_keys() -> list[str]:
    """
    Configured launch secrets, newest first.

    Use HRIS_LAUNCH_SECRET_KEYS for rotation (comma-separated). Falls back to
    HRIS_LAUNCH_SECRET_KEY when unset.
    """
    raw = (settings.HRIS_LAUNCH_SECRET_KEYS or "").strip()
    if raw:
        keys = [k.strip() for k in raw.split(",") if k.strip()]
        if keys:
            return keys
    single = (settings.HRIS_LAUNCH_SECRET_KEY or "").strip()
    return [single] if single else []


def decrypt_hris_payload_with_configured_secrets(payload_b64: str) -> dict[str, Any]:
    """Try each configured secret until decrypt succeeds (supports key rotation)."""
    secrets = list_hris_launch_secret_keys()
    if not secrets:
        raise HrisPayloadDecryptError("HRIS launch secret is not configured")

    last_err: Exception | None = None
    for secret in secrets:
        try:
            return decrypt_hris_payload(payload_b64, secret)
        except HrisPayloadDecryptError as exc:
            last_err = exc

    raise HrisPayloadDecryptError(
        "AES decrypt failed with all configured HRIS launch secrets — "
        "set HRIS_LAUNCH_SECRET_KEY (current PHP self::$secretKey) and optionally "
        "HRIS_LAUNCH_SECRET_KEYS with comma-separated current,previous keys during rotation"
    ) from last_err
