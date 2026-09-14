"""HRIS launch payload encrypt/decrypt round-trip (PHP-compatible)."""
from __future__ import annotations

import base64
import json
import os
import time

import pytest
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from app.core.config import settings
from app.services.hris_launch.crypto import (
    _resolve_aes_key,
    decrypt_hris_payload,
    decrypt_hris_payload_with_configured_secrets,
    HrisPayloadDecryptError,
)


def _encrypt_like_php(data: dict, secret_key_b64: str) -> str:
    """Mirror PHP encryptData with openssl_encrypt(..., options=0)."""
    key = base64.b64decode(secret_key_b64)
    iv = os.urandom(16)
    plain = json.dumps(data, separators=(",", ":")).encode("utf-8")
    padder = padding.PKCS7(128).padder()
    padded = padder.update(plain) + padder.finalize()
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    raw = encryptor.update(padded) + encryptor.finalize()
    inner_b64 = base64.b64encode(raw)
    return base64.b64encode(iv + inner_b64).decode("ascii")


@pytest.fixture
def launch_secret_b64() -> str:
    return base64.b64encode(b"0" * 32).decode("ascii")


def test_resolve_secret_when_plus_mangled_to_space() -> None:
    """Env files often turn '+' into space without quotes."""
    key = "hF8XgF3qX5VfUQ1H5u6f+2TzWvlfPxC1Cz9zHck5O4k"
    assert len(_resolve_aes_key(key.replace("+", " "))) == 32


def test_round_trip_decrypt(launch_secret_b64: str) -> None:
    payload = {
        "subdomain": "demo_tenant",
        "employee_id": "99",
        "permissions": ["warehouse_access"],
        "exp": int(time.time()) + 300,
    }
    encrypted = _encrypt_like_php(payload, launch_secret_b64)
    out = decrypt_hris_payload(encrypted, launch_secret_b64)
    assert out["subdomain"] == "demo_tenant"
    assert out["employee_id"] == "99"


def test_wrong_key_fails(launch_secret_b64: str) -> None:
    encrypted = _encrypt_like_php({"subdomain": "x"}, launch_secret_b64)
    other_key = base64.b64encode(b"1" * 32).decode("ascii")
    with pytest.raises(HrisPayloadDecryptError):
        decrypt_hris_payload(encrypted, other_key)


def test_decrypt_tries_multiple_configured_keys(
    launch_secret_b64: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    old_key = base64.b64encode(b"1" * 32).decode("ascii")
    new_key = launch_secret_b64
    encrypted = _encrypt_like_php({"subdomain": "demo_tenant", "employee_id": "1"}, new_key)
    monkeypatch.setattr(settings, "HRIS_LAUNCH_SECRET_KEY", "")
    monkeypatch.setattr(settings, "HRIS_LAUNCH_SECRET_KEYS", f"{old_key},{new_key}")
    out = decrypt_hris_payload_with_configured_secrets(encrypted)
    assert out["subdomain"] == "demo_tenant"
