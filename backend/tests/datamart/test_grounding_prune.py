"""Tests for grounding prune (dim_employee vs mart)."""
from app.services.ai_services.datamart.semantic.grounding_prune import (
    filter_dimension_bindings,
    prune_thin_employee_dimensions,
)
from app.services.ai_services.datamart.schema_broker import SchemaGrounding

_THIN_DIM_COLS = [
    "loaded_at",
    "source_updated_at",
    "attendance_group_id",
    "basic_salary",
    "branch",
]

_MART_COLS = [
    "emp_fullname",
    "emp_no",
    "superior_emp_no",
    "superior_fullname",
    "designation",
    "probation_due_date",
    "grade_name",
    "location_name",
    "is_active",
]


def _grounding_with_both() -> SchemaGrounding:
    return SchemaGrounding(
        columns_by_table={
            "hr.dim_employee": list(_THIN_DIM_COLS),
            "hr.mart_employee_current": list(_MART_COLS),
        },
        dimension_bindings=[
            ("reporting_manager", "dim_employee", "manager_emp_no"),
            ("employee_name", "mart_employee_current", "emp_fullname"),
        ],
        source="test",
    )


def test_prune_drops_thin_dim_when_mart_rich():
    g = prune_thin_employee_dimensions(
        _grounding_with_both(),
        "List employees on probation with manager name",
    )
    shorts = {s.lower() for s in g.table_short_names}
    assert "mart_employee_current" in shorts
    assert "dim_employee" not in shorts


def test_filter_bindings_remaps_dim_to_mart():
    g = filter_dimension_bindings(_grounding_with_both())
    tables = {t for _, t, _ in g.dimension_bindings}
    assert "dim_employee" not in tables
    assert any(t == "mart_employee_current" for t in tables)
