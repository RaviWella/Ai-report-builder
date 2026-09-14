"""Each tenant resolves to its own hrm_wh_* database name."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.ai_services.datamart.workspace.runtime_context import (
    _tenant_warehouse_database_name,
    resolve_datamart_context,
)


def test_tenant_warehouse_db_name_uses_prefix():
    with patch(
        "app.core.warehouse.get_layout_sync",
        return_value=MagicMock(
            uses_dedicated_database=True,
            database_name="hrm_wh_acme_corp",
        ),
    ):
        assert _tenant_warehouse_database_name("acme_corp") == "hrm_wh_acme_corp"


def test_demo_tenant_default_db_name():
    with patch(
        "app.core.warehouse.get_layout_sync",
        return_value=MagicMock(
            uses_dedicated_database=True,
            database_name="hrm_wh_demo_tenant",
        ),
    ):
        assert _tenant_warehouse_database_name("demo_tenant") == "hrm_wh_demo_tenant"


def test_resolve_context_uses_registry_db_for_real_tenant(monkeypatch):
    monkeypatch.setattr("app.services.ai_services.datamart.config.DATAMART_PROFILE", "tenant_etl")
    monkeypatch.setattr("app.services.ai_services.datamart.config.DATAMART_LEGACY_FALLBACK", False)
    reg_engine = MagicMock()
    with patch(
        "app.services.ai_services.datamart.workspace.runtime_context._engine_from_datamart_env",
        return_value=(MagicMock(), "hrm_wh_demo_tenant"),
    ), patch(
        "app.services.ai_services.datamart.workspace.runtime_context._tenant_etl_ready_via_registry",
        return_value=True,
    ), patch(
        "app.services.ai_services.datamart.workspace.runtime_context._engine_for_tenant_registry",
        return_value=(reg_engine, "hrm_wh_real_customer"),
    ):
        ctx = resolve_datamart_context("real_customer")
    assert ctx.database_name == "hrm_wh_real_customer"
    assert ctx.engine is reg_engine
