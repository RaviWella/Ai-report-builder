"""
Phase 10 — live warehouse verification (opt-in).

Requires a reachable analytics warehouse (DATAMART_DB_* or tenant_registry) and:

  set DATAMART_LIVE_TEST=1
  pytest tests/datamart/test_live_smoke.py -m live -v

Optional HTTP check against a running API:

  set DATAMART_SMOKE_URL=http://127.0.0.1:8000

Expect tenant ETL (default checklist):

  set DATAMART_LIVE_EXPECT_PROFILE=tenant_etl

Legacy audit warehouse:

  set DATAMART_LIVE_EXPECT_PROFILE=legacy_audit
"""
from __future__ import annotations

import os

import pytest
import requests
from sqlalchemy import inspect as sa_inspect
from app.services.ai_services.datamart.workspace.runtime_context import (
    DatamartProfile,
    clear_metadata_cache_for_tests,
    invalidate_datamart_engines_for_tests,
    reset_datamart_context,
    resolve_datamart_context,
    run_with_datamart_context,
    set_datamart_context,
    sync_datamart_metadata,
)
from app.services.ai_services.datamart.schema import execute_sql

from .live_helpers import (
    apply_real_datamart_env,
    live_api_key,
    live_enabled,
    live_expect_profile,
    live_smoke_url,
    live_tenant_id,
)

pytestmark = [pytest.mark.datamart, pytest.mark.live]


@pytest.fixture(autouse=True)
def _live_real_datamart_profile(monkeypatch):
    if not live_enabled():
        pytest.skip("Set DATAMART_LIVE_TEST=1 to run Phase 10 live smoke tests")
    apply_real_datamart_env(monkeypatch)
    clear_metadata_cache_for_tests()
    invalidate_datamart_engines_for_tests()
    yield
    clear_metadata_cache_for_tests()
    invalidate_datamart_engines_for_tests()


def _assert_profile(ctx, meta: dict) -> None:
    expected = live_expect_profile()
    assert meta["profile"] == expected, (
        f"Expected profile={expected!r}, got {meta['profile']!r}. "
        "Check DATAMART_DB_* / tenant_registry / DATAMART_PROFILE."
    )
    assert ctx.profile.value == expected
    if expected == DatamartProfile.TENANT_ETL.value:
        schemas = {s.lower() for s in meta["query_schemas"]}
        assert "hr_semantic" in schemas
        assert "hr" in schemas
        assert "public_mint_audit" not in schemas
        assert meta["database_name"].startswith("hrm_wh_")


def test_live_bootstrap_metadata_inprocess():
    tenant = live_tenant_id()
    ctx = resolve_datamart_context(tenant)
    token = set_datamart_context(ctx)
    try:
        meta = sync_datamart_metadata(tenant)
    finally:
        reset_datamart_context(token)

    assert meta["tenant_id"] == tenant
    assert meta["ready"] is True, meta
    assert meta["total_tables"] > 0, meta.get("table_counts")
    _assert_profile(ctx, meta)


def test_live_etl_schema_has_tables():
    if live_expect_profile() != DatamartProfile.TENANT_ETL.value:
        pytest.skip("ETL schema probe only when DATAMART_LIVE_EXPECT_PROFILE=tenant_etl")

    tenant = live_tenant_id()

    def _probe() -> None:
        from app.services.ai_services.datamart.workspace.runtime_context import require_datamart_context

        ctx = require_datamart_context()
        inspector = sa_inspect(ctx.engine)
        semantic_tables = inspector.get_table_names(schema="hr_semantic")
        semantic_views = inspector.get_view_names(schema="hr_semantic")
        assert semantic_tables or semantic_views, (
            "hr_semantic has no tables/views — run ETL or fix DATAMART_DB_*"
        )
        hr_tables = inspector.get_table_names(schema="hr")
        hr_views = inspector.get_view_names(schema="hr")
        assert hr_tables or hr_views, "hr schema has no tables/views — run ETL"

    run_with_datamart_context(tenant, _probe)


def test_live_readonly_sql_uses_etl_schema():
    if live_expect_profile() != DatamartProfile.TENANT_ETL.value:
        pytest.skip("SQL schema probe only when DATAMART_LIVE_EXPECT_PROFILE=tenant_etl")

    tenant = live_tenant_id()
    sql = """
        SELECT table_schema, table_name
        FROM information_schema.tables
        WHERE table_schema IN ('hr_semantic', 'hr')
          AND table_type IN ('BASE TABLE', 'VIEW')
        LIMIT 1
    """

    def _run() -> None:
        cols, rows, count = execute_sql(sql)
        assert count >= 1, "No hr_semantic/hr tables visible to datamart reader"
        assert "table_schema" in [c.lower() for c in cols]

    run_with_datamart_context(tenant, _run)


@pytest.mark.asyncio
async def test_live_bootstrap_route_handler():
    """Same path as GET /api/v1/datamart/bootstrap (handler + response model)."""
    from app.api.routes.datamart_chat import datamart_bootstrap

    tenant = live_tenant_id()
    ctx = resolve_datamart_context(tenant)
    token = set_datamart_context(ctx)
    try:
        resp = await datamart_bootstrap()
    finally:
        reset_datamart_context(token)

    assert resp.ready is True
    assert resp.total_tables > 0
    assert resp.profile == live_expect_profile()
    assert resp.tenant_id == tenant


@pytest.mark.skipif(not live_smoke_url(), reason="Set DATAMART_SMOKE_URL for remote API smoke")
def test_live_http_bootstrap_remote():
    tenant = live_tenant_id()
    url = f"{live_smoke_url()}/api/v1/datamart/bootstrap"
    resp = requests.get(
        url,
        headers={
            "X-API-Key": live_api_key(),
            "X-Tenant-Id": tenant,
        },
        timeout=60,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ready"] is True
    assert body["profile"] == live_expect_profile()


@pytest.mark.skipif(
    os.getenv("DATAMART_LIVE_CHAT", "").strip().lower() not in ("1", "true", "yes"),
    reason="Set DATAMART_LIVE_CHAT=1 to run one LLM chat turn (slow)",
)
def test_live_chat_one_turn_remote():
    base = live_smoke_url()
    if not base:
        pytest.skip("DATAMART_SMOKE_URL required for live chat smoke")
    tenant = live_tenant_id()
    resp = requests.post(
        f"{base}/api/v1/datamart/chat",
        headers={
            "X-API-Key": live_api_key(),
            "X-Tenant-Id": tenant,
            "Content-Type": "application/json",
        },
        json={"question": "Reply with exactly: LIVE_OK", "session_id": None},
        timeout=int(os.getenv("DATAMART_LIVE_CHAT_TIMEOUT", "180")),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert not body.get("error"), body.get("error")
    sql = (body.get("sql_script") or "").lower()
    if live_expect_profile() == DatamartProfile.TENANT_ETL.value and sql:
        assert "public_mint_audit" not in sql
        assert "hr_semantic." in sql or " hr." in sql or sql.startswith("hr.")
