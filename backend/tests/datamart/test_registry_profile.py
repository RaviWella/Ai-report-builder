"""Phase 7: registry-first profile resolution."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.ai_services.datamart.workspace.runtime_context import (
    DatamartProfile,
    clear_metadata_cache_for_tests,
    invalidate_datamart_engines_for_tests,
    resolve_datamart_context,
)


def setup_function():
    clear_metadata_cache_for_tests()
    invalidate_datamart_engines_for_tests()


def teardown_function():
    clear_metadata_cache_for_tests()
    invalidate_datamart_engines_for_tests()


def test_registry_only_skips_env_tenant_etl(monkeypatch):
    monkeypatch.setattr("app.services.ai_services.datamart.config.DATAMART_PROFILE", "auto")
    monkeypatch.setattr("app.services.ai_services.datamart.config.DATAMART_LEGACY_FALLBACK", True)
    monkeypatch.setattr(
        "app.services.ai_services.datamart.config.DATAMART_USE_TENANT_REGISTRY",
        True,
    )
    with patch(
        "app.services.ai_services.datamart.workspace.runtime_context._engine_from_datamart_env",
        return_value=(MagicMock(), "hrm_wh_demo_tenant"),
    ), patch(
        "app.services.ai_services.datamart.workspace.runtime_context._tenant_etl_ready_via_registry",
        return_value=False,
    ), patch(
        "app.services.ai_services.datamart.workspace.runtime_context._tenant_etl_ready_via_env",
        return_value=True,
    ) as env_probe:
        ctx = resolve_datamart_context("demo_tenant")
    env_probe.assert_not_called()
    assert ctx.profile == DatamartProfile.LEGACY_AUDIT


def test_tenant_registry_available_helper(monkeypatch):
    monkeypatch.setattr(
        "app.core.warehouse.get_layout_sync",
        lambda tid: MagicMock(uses_dedicated_database=True, database_name="hrm_wh_x"),
    )
    from app.services.ai_services.datamart.workspace.runtime_context import tenant_registry_available

    assert tenant_registry_available("demo_tenant") is True


def test_prefer_env_uses_datamart_db_before_registry(monkeypatch):
    monkeypatch.setattr("app.services.ai_services.datamart.config.DATAMART_PROFILE", "auto")
    monkeypatch.setattr(
        "app.services.ai_services.datamart.config.DATAMART_PREFER_TENANT_REGISTRY",
        False,
    )
    monkeypatch.setattr(
        "app.services.ai_services.datamart.config.DATAMART_USE_TENANT_REGISTRY",
        False,
    )
    reg_engine = MagicMock(name="registry_engine")
    with patch(
        "app.services.ai_services.datamart.workspace.runtime_context._engine_from_datamart_env",
        return_value=(MagicMock(name="legacy_env_engine"), "hrm_wh_demo_tenant"),
    ), patch(
        "app.services.ai_services.datamart.workspace.runtime_context._tenant_etl_ready_via_registry",
        return_value=True,
    ), patch(
        "app.services.ai_services.datamart.workspace.runtime_context._tenant_etl_ready_via_env",
        return_value=True,
    ), patch(
        "app.services.ai_services.datamart.workspace.runtime_context._engine_for_tenant_registry",
        return_value=(reg_engine, "hrm_wh_registry"),
    ), patch(
        "app.services.ai_services.datamart.workspace.runtime_context.probe_tenant_etl_ready",
        return_value=True,
    ):
        ctx = resolve_datamart_context("demo_tenant")
    assert ctx.profile == DatamartProfile.TENANT_ETL
    assert ctx.database_name == "hrm_wh_demo_tenant"
    assert ctx.engine is not reg_engine


def test_registry_only_uses_tenant_etl_when_registry_ready(monkeypatch):
    monkeypatch.setattr("app.services.ai_services.datamart.config.DATAMART_PROFILE", "auto")
    monkeypatch.setattr(
        "app.services.ai_services.datamart.config.DATAMART_USE_TENANT_REGISTRY",
        True,
    )
    reg_engine = MagicMock()
    with patch(
        "app.services.ai_services.datamart.workspace.runtime_context._engine_from_datamart_env",
        return_value=(MagicMock(), "warehouse"),
    ), patch(
        "app.services.ai_services.datamart.workspace.runtime_context._tenant_etl_ready_via_registry",
        return_value=True,
    ), patch(
        "app.services.ai_services.datamart.workspace.runtime_context._engine_for_tenant_registry",
        return_value=(reg_engine, "hrm_wh_demo_tenant"),
    ):
        ctx = resolve_datamart_context("demo_tenant")
    assert ctx.profile == DatamartProfile.TENANT_ETL
    assert ctx.engine is reg_engine
    assert ctx.database_name == "hrm_wh_demo_tenant"
