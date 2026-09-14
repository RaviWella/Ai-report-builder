"""Table-scoped binding — no cross-table column bleed."""
from app.services.ai_services.datamart.schema_broker import SchemaGrounding
from app.services.ai_services.datamart.sql.sql_binding import validate_sql_bindings
from app.services.ai_services.datamart.sql.sql_column_allowlist import (
    resolve_column_for_table,
    try_rewrite_unknown_columns,
)


def test_unqualified_full_name_rejected_on_payroll_view_only():
    grounding = SchemaGrounding(
        columns_by_table={
            "hr_semantic.vw_payroll_summary": [
                "emp_fullname",
                "employee_id",
                "payroll_group_name",
                "basic_salary",
            ],
            "hr.mart_employee_current": [
                "emp_fullname",
                "full_name",
                "employee_id",
            ],
        },
        source="test",
    )
    sql = """
    SELECT full_name AS employee_name, employee_id, basic_salary
    FROM hr_semantic.vw_payroll_summary
    LIMIT 10
    """
    err = validate_sql_bindings(sql, grounding)
    assert err is not None
    assert "full_name" in err.lower() or "not on the table" in err.lower()


def test_resolve_full_name_to_emp_fullname_on_payroll_view():
    grounding = SchemaGrounding(
        columns_by_table={
            "hr_semantic.vw_payroll_summary": [
                "emp_fullname",
                "employee_id",
                "basic_salary",
            ],
        },
        source="test",
    )
    assert (
        resolve_column_for_table("full_name", "vw_payroll_summary", grounding)
        == "emp_fullname"
    )


def test_rewrite_unknown_column_in_select_list():
    grounding = SchemaGrounding(
        columns_by_table={
            "hr_semantic.vw_payroll_summary": [
                "emp_fullname",
                "employee_id",
                "basic_salary",
            ],
        },
        source="test",
    )
    sql = (
        "SELECT full_name AS employee_name, employee_id "
        "FROM hr_semantic.vw_payroll_summary LIMIT 10"
    )
    out = try_rewrite_unknown_columns(sql, grounding)
    assert out is not None
    assert "emp_fullname" in out
    assert "full_name" not in out.lower().split("from")[0]
