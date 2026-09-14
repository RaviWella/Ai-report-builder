"""Semantic catalog sync service (Sync button backend)."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from app.services.ai_services.datamart.semantic.semantic_catalog_sync import (
    _refresh_report_to_dict,
    refresh_semantic_catalog_for_tenant,
)


def test_refresh_report_to_dict_ok_when_no_validation_issues():
    report = MagicMock(
        missing_tables=[],
        unknown_columns={},
        topics_tables_added={"employee_information": ["mart_employee_current"]},
        topics_tables_removed={},
        joins_added=["a|b|c|d"],
        dimension_stubs_added=[],
        removed_dimensions=[],
        warehouse_only_tables=[],
    )
    out = _refresh_report_to_dict(report, Path("/tmp/demo_tenant.yaml"))
    assert out["ok"] is True
    assert out["joins_added"] == 1
    assert "mart_employee_current" in str(out["topics_tables_added"])


def test_refresh_semantic_catalog_for_tenant_calls_tool_write():
    fake_snap = MagicMock(tables=["mart_employee_current"], schema="hr,hr_semantic")
    fake_report = MagicMock(
        missing_tables=[],
        unknown_columns={},
        topics_tables_added={},
        topics_tables_removed={},
        joins_added=[],
        dimension_stubs_added=[],
        removed_dimensions=[],
        warehouse_only_tables=[],
    )
    fake_tool = MagicMock()
    fake_tool._snapshot_warehouse.return_value = fake_snap
    fake_tool._load_catalog_for_command.return_value = {"topics": {}}
    fake_tool.refresh_catalog.return_value = fake_report

    with patch(
        "app.services.ai_services.datamart.semantic.semantic_catalog_sync._catalog_tool",
        return_value=fake_tool,
    ), patch(
        "app.services.ai_services.datamart.semantic.semantic_catalog_sync.catalog_path_for_tenant_cli",
        return_value=Path("semantic_catalogs/demo_tenant.yaml"),
    ):
        out = refresh_semantic_catalog_for_tenant("demo_tenant")
    assert out["ok"] is True
    assert out["table_count"] == 1
    fake_tool._save_catalog.assert_called_once()
