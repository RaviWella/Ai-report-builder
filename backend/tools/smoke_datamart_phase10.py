#!/usr/bin/env python
"""
Phase 10 datamart smoke — bootstrap + optional HTTP / chat checks.

Run from backend/ (loads .env via app settings):

  python tools/smoke_datamart_phase10.py
  python tools/smoke_datamart_phase10.py --url http://127.0.0.1:8000
  python tools/smoke_datamart_phase10.py --chat --url http://127.0.0.1:8000

Environment:
  DATAMART_LIVE_TENANT_ID       (default demo_tenant)
  DATAMART_LIVE_EXPECT_PROFILE  (default tenant_etl)
  DATAMART_SMOKE_API_KEY        (default settings.API_KEY)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

# Allow `python tools/smoke_datamart_phase10.py` from backend/
_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)


def _ok(msg: str) -> None:
    print(f"  OK  {msg}")


def _fail(msg: str) -> int:
    print(f"  FAIL {msg}", file=sys.stderr)
    return 1


def _prepare_smoke_runtime() -> None:
    """Reload .env and prefer DATAMART_DB_* for smoke (developer warehouse)."""
    _load_env()
    os.environ["DATAMART_PREFER_TENANT_REGISTRY"] = "false"
    from app.services.ai_services.datamart.workspace.runtime_context import (
        clear_metadata_cache_for_tests,
        invalidate_datamart_engines_for_tenant,
    )

    clear_metadata_cache_for_tests()
    tenant = (os.getenv("DATAMART_LIVE_TENANT_ID") or "demo_tenant").strip()
    invalidate_datamart_engines_for_tenant(tenant)
    # Re-read datamart config after .env load
    import importlib
    from app.services.ai_services.datamart import config as dm_config

    importlib.reload(dm_config)


def check_inprocess(tenant: str, expect_profile: str) -> int:
    from app.services.ai_services.datamart.workspace.runtime_context import (
        resolve_datamart_context,
        sync_datamart_metadata,
    )

    _prepare_smoke_runtime()
    print("==> In-process bootstrap")
    ctx = resolve_datamart_context(tenant)
    meta = sync_datamart_metadata(tenant)
    if meta.get("profile") != expect_profile:
        return _fail(
            f"profile={meta.get('profile')!r} expected {expect_profile!r} "
            "(check DATAMART_DB_* / tenant_registry / DATAMART_PROFILE)"
        )
    if not meta.get("ready"):
        return _fail(f"ready=false table_counts={meta.get('table_counts')}")
    if meta.get("total_tables", 0) < 1:
        return _fail("total_tables=0")
    if expect_profile == "tenant_etl":
        schemas = {s.lower() for s in meta.get("query_schemas") or []}
        if "hr_semantic" not in schemas or "hr" not in schemas:
            return _fail(f"query_schemas missing ETL layout: {meta.get('query_schemas')}")
        if "public_mint_audit" in schemas:
            return _fail("legacy schema public_mint_audit in query_schemas")
        dbn = meta.get("database_name") or ""
        if not dbn.startswith("hrm_wh_"):
            return _fail(f"database_name={dbn!r} (expected hrm_wh_*)")
    _ok(
        f"tenant={tenant} profile={meta['profile']} db={meta['database_name']} "
        f"tables={meta['total_tables']}"
    )
    return 0


def check_http(url: str, tenant: str, expect_profile: str, api_key: str) -> int:
    import requests

    print(f"==> HTTP GET {url}/api/v1/datamart/bootstrap")
    try:
        resp = requests.get(
            f"{url.rstrip('/')}/api/v1/datamart/bootstrap",
            headers={"X-API-Key": api_key, "X-Tenant-Id": tenant},
            timeout=60,
        )
    except requests.RequestException as exc:
        return _fail(f"bootstrap request failed: {exc}")
    if resp.status_code != 200:
        return _fail(f"HTTP {resp.status_code}: {resp.text[:500]}")
    body = resp.json()
    if body.get("profile") != expect_profile:
        return _fail(f"profile={body.get('profile')!r}")
    if not body.get("ready"):
        return _fail(json.dumps(body, indent=2)[:800])
    _ok(f"bootstrap ready={body['ready']} tables={body.get('total_tables')}")
    return 0


def check_chat(url: str, tenant: str, expect_profile: str, api_key: str, timeout: int) -> int:
    import requests

    print(f"==> HTTP POST {url}/api/v1/datamart/chat (short)")
    try:
        resp = requests.post(
            f"{url.rstrip('/')}/api/v1/datamart/chat",
            headers={
                "X-API-Key": api_key,
                "X-Tenant-Id": tenant,
                "Content-Type": "application/json",
            },
            json={"question": "Reply with exactly: LIVE_OK", "session_id": None},
            timeout=timeout,
        )
    except requests.RequestException as exc:
        return _fail(f"chat request failed: {exc}")
    if resp.status_code != 200:
        return _fail(f"HTTP {resp.status_code}: {resp.text[:500]}")
    body = resp.json()
    if body.get("error"):
        return _fail(f"chat error: {body.get('error')}")
    sql = (body.get("sql_script") or "").lower()
    if expect_profile == "tenant_etl" and sql and "public_mint_audit" in sql:
        return _fail(f"SQL used legacy schema: {body.get('sql_script')[:200]}")
    _ok(f"chat ok narrative={(body.get('narrative') or '')[:80]!r}")
    return 0


def _load_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(os.path.join(_BACKEND, ".env"))


def main(argv: list[str] | None = None) -> int:
    _load_env()
    parser = argparse.ArgumentParser(description="Phase 10 datamart live smoke")
    parser.add_argument(
        "--url",
        default=os.getenv("DATAMART_SMOKE_URL", "").strip(),
        help="Running API base URL (optional)",
    )
    parser.add_argument("--tenant", default=os.getenv("DATAMART_LIVE_TENANT_ID", "demo_tenant"))
    parser.add_argument(
        "--expect-profile",
        default=os.getenv("DATAMART_LIVE_EXPECT_PROFILE", "tenant_etl"),
    )
    parser.add_argument("--chat", action="store_true", help="One /datamart/chat turn (slow)")
    parser.add_argument("--chat-timeout", type=int, default=180)
    parser.add_argument("--skip-inprocess", action="store_true")
    args = parser.parse_args(argv)
    url = (args.url or "").strip()
    if url and not (url.startswith("http://") or url.startswith("https://")):
        url = ""

    from app.core.config import settings

    api_key = (os.getenv("DATAMART_SMOKE_API_KEY") or settings.API_KEY or "").strip()
    if not api_key:
        return _fail("No API key (DATAMART_SMOKE_API_KEY or settings.API_KEY)")

    rc = 0
    if not args.skip_inprocess:
        rc = check_inprocess(args.tenant, args.expect_profile)
        if rc:
            return rc

    if url:
        rc = check_http(url, args.tenant, args.expect_profile, api_key)
        if rc:
            return rc
        if args.chat:
            rc = check_chat(url, args.tenant, args.expect_profile, api_key, args.chat_timeout)
            if rc:
                return rc

    print("Phase 10 smoke passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
