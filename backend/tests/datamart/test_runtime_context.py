"""Tests for datamart runtime profile resolution and multi-schema helpers."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.ai_services.datamart.workspace.runtime_context import (
    DatamartProfile,
    DatamartRuntimeContext,
    clear_metadata_cache_for_tests,
    database_prompt_section,
    invalidate_datamart_engines_for_tests,
    reset_datamart_context,
    resolve_datamart_context,
    run_with_datamart_context,
    set_datamart_context,
    sql_qualification_rule,
)


def _mock_ctx(*, profile: DatamartProfile) -> DatamartRuntimeContext:
    schemas = (
        ("hr_semantic", "hr", "hr_snap")
        if profile == DatamartProfile.TENANT_ETL
        else ("public_mint_audit",)
    )
    primary = schemas[0]
    return DatamartRuntimeContext(
        tenant_id="demo_tenant",
        profile=profile,
        engine=MagicMock(),
        query_schemas=schemas,
        primary_schema=primary,
        database_name="hrm_wh_demo_tenant",
    )


def setup_function():
    clear_metadata_cache_for_tests()
    invalidate_datamart_engines_for_tests()


def teardown_function():
    clear_metadata_cache_for_tests()
    invalidate_datamart_engines_for_tests()


def test_resolve_legacy_profile_explicit(monkeypatch):
    monkeypatch.setenv("DATAMART_PROFILE", "legacy_audit")
    with patch(
        "app.services.ai_services.datamart.workspace.runtime_context._engine_from_datamart_env",
        return_value=(MagicMock(), "warehouse"),
    ):
        ctx = resolve_datamart_context("demo_tenant")
    assert ctx.profile == DatamartProfile.LEGACY_AUDIT
    assert ctx.query_schemas == ("public_mint_audit",)


def test_resolve_tenant_etl_profile_explicit(monkeypatch):
    monkeypatch.setenv("DATAMART_QUERY_SCHEMAS", "hr_semantic,hr,hr_snap")
    with patch(
        "app.services.ai_services.datamart.workspace.runtime_context._resolve_profile",
        return_value=DatamartProfile.TENANT_ETL,
    ), patch(
        "app.services.ai_services.datamart.workspace.runtime_context._engine_from_datamart_env",
        return_value=(MagicMock(), "hrm_wh_demo_tenant"),
    ), patch(
        "app.services.ai_services.datamart.workspace.runtime_context._engine_for_tenant_registry",
        return_value=None,
    ):
        ctx = resolve_datamart_context("demo_tenant")
    assert ctx.profile == DatamartProfile.TENANT_ETL
    assert ctx.query_schemas == ("hr_semantic", "hr", "hr_snap")
    assert ctx.primary_schema == "hr_semantic"


def test_database_prompt_section_tenant_etl():
    ctx = _mock_ctx(profile=DatamartProfile.TENANT_ETL)
    token = set_datamart_context(ctx)
    try:
        text = database_prompt_section()
        assert "hr_semantic" in text
        assert "hr_snap" in text
        rule = sql_qualification_rule()
        assert "hr_semantic" in rule
    finally:
        reset_datamart_context(token)


def test_run_with_datamart_context_sets_contextvar():
    calls: list[str] = []

    def _fn():
        from app.services.ai_services.datamart.workspace.runtime_context import get_datamart_context

        ctx = get_datamart_context()
        calls.append(ctx.tenant_id if ctx else "")
        return "ok"

    with patch(
        "app.services.ai_services.datamart.workspace.runtime_context.resolve_datamart_context",
        return_value=_mock_ctx(profile=DatamartProfile.TENANT_ETL),
    ):
        out = run_with_datamart_context("demo_tenant", _fn)
    assert out == "ok"
    assert calls == ["demo_tenant"]
