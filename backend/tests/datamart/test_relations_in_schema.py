"""Schema introspection includes base tables and views (hr_semantic is view-only)."""
from __future__ import annotations

from unittest.mock import MagicMock

from app.services.ai_services.datamart.schema import relations_in_schema


def test_relations_in_schema_merges_tables_and_views_deduped():
    inspector = MagicMock()
    inspector.get_table_names.return_value = ["fact_payroll", "vw_headcount"]
    inspector.get_view_names.return_value = ["vw_headcount", "vw_attendance"]

    names = relations_in_schema(inspector, "hr_semantic")
    assert names == ["fact_payroll", "vw_headcount", "vw_attendance"]


def test_relations_in_schema_view_only_schema():
    inspector = MagicMock()
    inspector.get_table_names.return_value = []
    inspector.get_view_names.return_value = ["vw_a", "vw_b"]

    assert relations_in_schema(inspector, "hr_semantic") == ["vw_a", "vw_b"]
