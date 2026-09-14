#!/usr/bin/env python
"""
Test whether HRIS_LAUNCH_SECRET_KEY can decrypt a launch payload from MinHRM.

Usage (from backend/):
  python tools/verify_hris_launch_secret.py --payload "BASE64..."
  python tools/verify_hris_launch_secret.py --payload "BASE64..." --secret "PHP_SECRET_B64"
"""
from __future__ import annotations

import argparse
import json
import os
import sys

_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)


def main() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv(os.path.join(_BACKEND, ".env"))
    except ImportError:
        pass

    from app.core.config import settings
    from app.services.hris_launch.crypto import (
        HrisPayloadDecryptError,
        decrypt_hris_payload,
        decrypt_hris_payload_with_configured_secrets,
        list_hris_launch_secret_keys,
    )

    parser = argparse.ArgumentParser(description="Verify HRIS launch secret against a payload")
    parser.add_argument("--payload", required=True, help="payload query param (base64)")
    parser.add_argument(
        "--secret",
        default="",
        help="Override secret (default: HRIS_LAUNCH_SECRET_KEY from .env)",
    )
    args = parser.parse_args()

    secret = (args.secret or "").strip()
    try:
        if secret:
            data = decrypt_hris_payload(args.payload, secret)
        elif list_hris_launch_secret_keys():
            data = decrypt_hris_payload_with_configured_secrets(args.payload)
        else:
            raise SystemExit(
                "No secret: pass --secret or set HRIS_LAUNCH_SECRET_KEY / HRIS_LAUNCH_SECRET_KEYS in backend/.env"
            )
    except HrisPayloadDecryptError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    print("OK — decrypted JSON:")
    print(json.dumps(data, indent=2, default=str))


if __name__ == "__main__":
    main()
