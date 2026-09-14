#!/usr/bin/env python
"""
Issue a dev JWT for datamart / HR API testing (MOCK_AUTH_ENABLED=false).

Usage (from backend/):
  python tools/create_dev_jwt.py --tenant-id demo_tenant --user-id user-42
  python tools/create_dev_jwt.py --tenant-id demo_tenant --print-curl
"""
from __future__ import annotations

import argparse
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
    from app.core.security import create_access_token

    parser = argparse.ArgumentParser(description="Create dev access JWT")
    parser.add_argument("--tenant-id", default="demo_tenant")
    parser.add_argument("--user-id", default="dev-user-001")
    parser.add_argument("--email", default="")
    parser.add_argument("--role", default="admin")
    parser.add_argument("--minutes", type=int, default=None)
    parser.add_argument("--print-curl", action="store_true")
    args = parser.parse_args()

    token = create_access_token(
        tenant_id=args.tenant_id.strip(),
        user_id=args.user_id.strip(),
        email=args.email.strip() or None,
        role=args.role,
        expires_minutes=args.minutes,
    )
    print(token)
    if args.print_curl:
        api_key = settings.API_KEY
        print(
            f'\ncurl -H "Authorization: Bearer {token}" '
            f'-H "X-API-Key: {api_key}" '
            f'-H "X-Tenant-Id: {args.tenant_id}" '
            f"http://127.0.0.1:8000/api/v1/datamart/bootstrap"
        )


if __name__ == "__main__":
    main()
