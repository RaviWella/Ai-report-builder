"""Employee + shift list SQL template."""
from app.services.ai_services.datamart.schema_broker import SchemaGrounding
from app.services.ai_services.datamart.domain_sql.employee_shift_sql import (
    try_build_employee_shift_list_sql,
)
from app.services.ai_services.datamart.sql.sql_fast_path import try_resolve_deterministic_sql


def _shift_grounding() -> SchemaGrounding:
    return SchemaGrounding(
        columns_by_table={
            "hr_semantic.mart_employee_current": [
                "emp_no",
                "emp_fullname",
                "shift_id",
                "is_current",
            ],
            "hr_semantic.dim_shift": [
                "source_shift_id",
                "shift_name",
            ],
        },
        source="test",
    )


def test_shift_list_joins_dim_shift():
    q = "List employee no, employee name and assigned shift name"
    sql = try_build_employee_shift_list_sql(q, grounding=_shift_grounding())
    assert sql is not None
    assert "mart_employee_current" in sql
    assert "dim_shift" in sql
    assert "shift_name" in sql
    assert "NULL::text" not in sql
    assert "dim_employee" not in sql


def test_fast_path_uses_shift_template():
    q = "List employee no, employee name and assigned shift name"
    resolved = try_resolve_deterministic_sql(q, grounding=_shift_grounding())
    assert resolved is not None
    assert resolved[1] == "employee_shift_template"


def test_shift_list_via_dim_employee_when_mart_lacks_shift_key():
    from app.services.ai_services.datamart.domain_sql.employee_shift_sql import (
        try_build_employee_shift_list_sql,
    )

    grounding = SchemaGrounding(
        columns_by_table={
            "hr.mart_employee_current": ["emp_no", "emp_fullname", "is_current"],
            "hr.dim_employee": [
                "emp_no",
                "emp_fullname",
                "shift_id",
                "is_current",
            ],
            "hr.dim_shift": ["source_shift_id", "shift_name", "is_current"],
        },
        source="test",
    )
    q = "List employee no, employee name and assigned shift name"
    sql = try_build_employee_shift_list_sql(q, grounding=grounding)
    assert sql is not None
    assert "dim_employee" in sql
    assert "source_shift_id::text = e.shift_id::text" in sql
    assert "shift_sk" not in sql
