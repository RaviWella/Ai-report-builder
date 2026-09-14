"""Employee detail-list SQL from mart_employee_current."""
from app.services.ai_services.datamart.domain_sql.employee_list_sql import (
    looks_like_employee_detail_list,
    try_build_employee_list_sql,
)
from app.services.ai_services.datamart.schema_broker import SchemaGrounding


def _mart_grounding() -> SchemaGrounding:
    return SchemaGrounding(
        columns_by_table={
            "hr_semantic.mart_employee_current": [
                "emp_no",
                "emp_fullname",
                "superior_fullname",
                "superior_emp_no",
                "is_current",
            ],
        },
        source="test",
    )


def test_supervisor_list_question():
    q = (
        "List down employee name, employee full name and "
        "reporting immediate supervisor"
    )
    g = _mart_grounding()
    assert looks_like_employee_detail_list(q, grounding=g)
    sql = try_build_employee_list_sql(q, grounding=g)
    assert sql is not None
    assert "mart_employee_current" in sql
    assert "superior_fullname" in sql
    assert "reporting_supervisor_name" in sql


def test_fast_path_resolves_supervisor_question():
    from app.services.ai_services.datamart.sql.sql_fast_path import try_resolve_deterministic_sql

    q = (
        "List down employee name, employee full name and "
        "reporting immediate supervisor"
    )
    resolved = try_resolve_deterministic_sql(q, grounding=_mart_grounding())
    assert resolved is not None
    assert resolved[1] == "employee_list_template"
