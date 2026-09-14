"""Phase 11 — per-tenant semantic catalog path resolution."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from app.services.ai_services.datamart.workspace.runtime_context import (
    DatamartProfile,
    DatamartRuntimeContext,
    reset_datamart_context,
    set_datamart_context,
)
from app.services.ai_services.datamart.semantic.semantic_catalog_paths import (
    LEGACY_CATALOG_PATH,
    catalog_path_for_tenant_cli,
    resolve_semantic_catalog_path,
    tenant_catalog_path,
)


def test_tenant_catalog_path_naming():
    p = tenant_catalog_path("demo_tenant")
    assert p.name == "demo_tenant.yaml"
    assert p.parent.name == "semantic_catalogs"


def test_legacy_profile_uses_packaged_catalog():
    ctx = DatamartRuntimeContext(
        tenant_id="demo_tenant",
        profile=DatamartProfile.LEGACY_AUDIT,
        engine=MagicMock(),
        query_schemas=("public_mint_audit",),
        primary_schema="public_mint_audit",
        database_name="warehouse",
    )
    token = set_datamart_context(ctx)
    try:
        assert resolve_semantic_catalog_path() == LEGACY_CATALOG_PATH
    finally:
        reset_datamart_context(token)


def test_tenant_etl_prefers_tenant_file_when_present(tmp_path, monkeypatch):
    tenant_file = tmp_path / "semantic_catalogs" / "acme.yaml"
    tenant_file.parent.mkdir(parents=True)
    tenant_file.write_text("topics: {}\n", encoding="utf-8")

    monkeypatch.setattr(
        "app.services.ai_services.datamart.semantic.semantic_catalog_paths.TENANT_CATALOG_DIR",
        tmp_path / "semantic_catalogs",
    )
    ctx = DatamartRuntimeContext(
        tenant_id="acme",
        profile=DatamartProfile.TENANT_ETL,
        engine=MagicMock(),
        query_schemas=("hr_semantic", "hr"),
        primary_schema="hr_semantic",
        database_name="hrm_wh_acme",
    )
    token = set_datamart_context(ctx)
    try:
        assert resolve_semantic_catalog_path() == tenant_file
        assert catalog_path_for_tenant_cli("acme") == tenant_file
    finally:
        reset_datamart_context(token)


def test_tenant_etl_uses_tenant_catalog_path_even_when_file_missing(monkeypatch):
    monkeypatch.setattr(
        "app.services.ai_services.datamart.semantic.semantic_catalog_paths.TENANT_CATALOG_DIR",
        Path("/nonexistent/semantic_catalogs"),
    )
    ctx = DatamartRuntimeContext(
        tenant_id="missing_tenant",
        profile=DatamartProfile.TENANT_ETL,
        engine=MagicMock(),
        query_schemas=("hr",),
        primary_schema="hr_semantic",
        database_name="hrm_wh_missing_tenant",
    )
    token = set_datamart_context(ctx)
    try:
        path = resolve_semantic_catalog_path()
        assert path == Path("/nonexistent/semantic_catalogs/missing_tenant.yaml")
        assert not path.is_file()
    finally:
        reset_datamart_context(token)
