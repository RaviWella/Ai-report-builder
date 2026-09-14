"""Bootstrap metadata payload shape (read-only introspection, no live DB)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.ai_services.datamart.workspace.runtime_context import (
    DatamartProfile,
    DatamartRuntimeContext,
    clear_metadata_cache_for_tests,
    sync_datamart_metadata,
)


def setup_function():
    clear_metadata_cache_for_tests()


def teardown_function():
    clear_metadata_cache_for_tests()


def test_sync_datamart_metadata_payload_shape():
    ctx = DatamartRuntimeContext(
        tenant_id="demo_tenant",
        profile=DatamartProfile.TENANT_ETL,
        engine=MagicMock(),
        query_schemas=("hr_semantic", "hr", "hr_snap"),
        primary_schema="hr_semantic",
        database_name="hrm_wh_demo_tenant",
    )
    inspector = MagicMock()

    def _names(schema=None):
        if schema == "hr_semantic":
            return ["vw_headcount"]
        if schema:
            return ["t1", "t2"]
        return []

    inspector.get_table_names.side_effect = _names
    inspector.get_view_names.side_effect = lambda schema=None: (
        ["vw_headcount"] if schema == "hr_semantic" else []
    )

    with patch(
        "app.services.ai_services.datamart.workspace.runtime_context.resolve_datamart_context",
        return_value=ctx,
    ), patch(
        "app.services.ai_services.datamart.workspace.runtime_context._schema_fingerprint",
        return_value="fp1",
    ), patch("sqlalchemy.inspect", return_value=inspector):
        payload = sync_datamart_metadata("demo_tenant")

    assert payload["tenant_id"] == "demo_tenant"
    assert payload["profile"] == "tenant_etl"
    assert payload["database_name"] == "hrm_wh_demo_tenant"
    assert payload["query_schemas"] == ["hr_semantic", "hr", "hr_snap"]
    assert payload["primary_schema"] == "hr_semantic"
    assert payload["ready"] is True
    assert payload["table_counts"]["hr_semantic"] == 1
    assert payload["total_tables"] == 5
    assert "synced_at" in payload
    assert "fingerprint" in payload


def test_sync_datamart_metadata_force_refresh_bypasses_ttl_cache():
    ctx = DatamartRuntimeContext(
        tenant_id="demo_tenant",
        profile=DatamartProfile.TENANT_ETL,
        engine=MagicMock(),
        query_schemas=("hr",),
        primary_schema="hr",
        database_name="hrm_wh_demo_tenant",
    )
    inspector = MagicMock()
    inspector.get_table_names.return_value = ["dim_employee"]
    inspector.get_view_names.return_value = []
    call_count = {"n": 0}

    def _fingerprint(*_args, **_kwargs):
        call_count["n"] += 1
        return f"fp{call_count['n']}"

    with patch(
        "app.services.ai_services.datamart.workspace.runtime_context.resolve_datamart_context",
        return_value=ctx,
    ), patch(
        "app.services.ai_services.datamart.workspace.runtime_context._schema_fingerprint",
        side_effect=_fingerprint,
    ), patch("sqlalchemy.inspect", return_value=inspector):
        first = sync_datamart_metadata("demo_tenant")
        second = sync_datamart_metadata("demo_tenant", force_refresh=True)

    assert first["fingerprint"] == "fp1"
    assert second["fingerprint"] == "fp2"
