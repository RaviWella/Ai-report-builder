#!/usr/bin/env python
"""
Build a PHP-compatible HRIS launch payload for local /auth testing.

Usage (from backend/):
  python tools/create_hris_launch_payload.py
  python tools/create_hris_launch_payload.py --tenant-id demo_tenant --employee-id 1001
  python tools/create_hris_launch_payload.py --print-url --port 5173
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
from urllib.parse import quote

_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)


def encrypt_like_php(data: dict, secret_key_b64: str) -> str:
    import os as _os

    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import padding
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

    key = base64.b64decode(secret_key_b64.strip())
    if len(key) != 32:
        raise SystemExit("HRIS_LAUNCH_SECRET_KEY must decode to 32 bytes for AES-256")

    iv = _os.urandom(16)
    plain = json.dumps(data, separators=(",", ":")).encode("utf-8")
    padder = padding.PKCS7(128).padder()
    padded = padder.update(plain) + padder.finalize()
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    raw = encryptor.update(padded) + encryptor.finalize()
    inner_b64 = base64.b64encode(raw)
    return base64.b64encode(iv + inner_b64).decode("ascii")


def main() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv(os.path.join(_BACKEND, ".env"))
    except ImportError:
        pass

    from app.core.config import settings

    parser = argparse.ArgumentParser(description="Create HRIS launch payload for /auth")
    parser.add_argument("--tenant-id", default="demo_tenant")
    parser.add_argument("--employee-id", default="1001")
    parser.add_argument("--minutes", type=int, default=5)
    parser.add_argument("--port", type=int, default=5173)
    parser.add_argument("--print-url", action="store_true")
    parser.add_argument("--print-curl", action="store_true")
    args = parser.parse_args()

    secret = (settings.HRIS_LAUNCH_SECRET_KEY or "").strip()
    if not secret:
        raise SystemExit(
            "HRIS_LAUNCH_SECRET_KEY is empty. Add it to backend/.env and restart the API."
        )

    now = int(time.time())
    data = {
        "subdomain": args.tenant_id,
        "tenant_id": args.tenant_id,
        "employee_id": args.employee_id,
        "permissions": ["warehouse_access"],
        "company_name": "Demo Company",
        "logo_url": "https://via.placeholder.com/64",
        "iat": now,
        "exp": now + args.minutes * 60,
    }
    payload = encrypt_like_php(data, secret)
    print(payload)
    if args.print_url:
        url = f"http://localhost:{args.port}/auth?payload={quote(payload, safe='')}"
        print(f"\nOpen in browser:\n{url}", file=sys.stderr)
    if args.print_curl:
        print(
            f'\ncurl -X POST http://127.0.0.1:8000/api/v1/auth/verify-payload '
            f'-H "X-API-Key: {settings.API_KEY}" -H "Content-Type: application/json" '
            f'-d {json.dumps({"payload": payload})!r}',
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
