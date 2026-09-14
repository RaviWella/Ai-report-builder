"""Phase 11 — tenant catalog loading and ETL-qualified join hints."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import yaml

from app.services.ai_services.datamart.workspace.runtime_context import (
    DatamartProfile,
    DatamartRuntimeContext,
    reset_datamart_context,
    set_datamart_context,
)
from app.services.ai_services.datamart.semantic.semantic_layer import (
    active_catalog_path,
    catalog_join_hints_for_tables,
    clear_catalog_cache,
    resolve_semantics,
)


def setup_function() -> None:
    clear_catalog_cache()


def teardown_function() -> None:
    clear_catalog_cache()


def _etl_ctx(tenant_id: str = "acme") -> DatamartRuntimeContext:
    return DatamartRuntimeContext(
        tenant_id=tenant_id,
        profile=DatamartProfile.TENANT_ETL,
        engine=MagicMock(),
        query_schemas=("hr_semantic", "hr", "hr_snap"),
        primary_schema="hr_semantic",
        database_name=f"hrm_wh_{tenant_id}",
    )


def test_active_catalog_path_points_at_tenant_file(tmp_path, monkeypatch):
    catalog_dir = tmp_path / "semantic_catalogs"
    catalog_dir.mkdir()
    tenant_file = catalog_dir / "acme.yaml"
    tenant_file.write_text(
        yaml.dump(
            {
                "topics": {
                    "payroll": {
                        "keywords": ["salary", "payroll"],
                        "tables": ["fact_payroll_detail"],
                    }
                },
                "dimensions": {},
                "metrics": {},
                "joins": [],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "app.services.ai_services.datamart.semantic.semantic_catalog_paths.TENANT_CATALOG_DIR",
        catalog_dir,
    )
    token = set_datamart_context(_etl_ctx("acme"))
    try:
        assert active_catalog_path() == tenant_file
        r = resolve_semantics("show top paid employees by basic salary")
        assert "fact_payroll_detail" in r.seed_tables
        assert "payroll" in r.topics_matched
    finally:
        reset_datamart_context(token)


def test_catalog_join_hints_use_etl_schema_prefixes(tmp_path, monkeypatch):
    catalog_dir = tmp_path / "semantic_catalogs"
    catalog_dir.mkdir()
    (catalog_dir / "acme.yaml").write_text(
        yaml.dump(
            {
                "topics": {},
                "dimensions": {},
                "metrics": {},
                "joins": [
                    {
                        "left_table": "dim_employee",
                        "left_column": "employee_id",
                        "right_table": "fact_payroll_detail",
                        "right_column": "employee_id",
                        "purpose": "payroll",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "app.services.ai_services.datamart.semantic.semantic_catalog_paths.TENANT_CATALOG_DIR",
        catalog_dir,
    )
    token = set_datamart_context(_etl_ctx("acme"))
    try:
        hints = catalog_join_hints_for_tables(["dim_employee", "fact_payroll_detail"])
        assert hints
        joined = hints[0]
        assert "hr.dim_employee" in joined
        assert "hr.fact_payroll_detail" in joined
        assert "public_mint_audit" not in joined
    finally:
        reset_datamart_context(token)
