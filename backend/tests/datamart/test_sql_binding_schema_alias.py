"""Binding across schema-qualified SQL vs short-name grounding keys."""
from __future__ import annotations

from app.services.ai_services.datamart.schema_broker import SchemaGrounding
from app.services.ai_services.datamart.sql.sql_binding import validate_sql_bindings
from app.services.ai_services.datamart.sql.sql_column_allowlist import try_rewrite_unknown_columns


def test_qualified_column_allowed_when_grounding_uses_different_schema():
    """SQL uses hr.* while grounding introspected hr_semantic.* — same short name."""
    grounding = SchemaGrounding(
        columns_by_table={
            "hr_semantic.vw_payroll_summary": [
                "emp_fullname",
                "emp_no",
                "basic_salary",
                "branch",
                "payroll_group_name",
            ],
        },
        source="test",
    )
    sql = (
        "SELECT v.emp_fullname, v.payroll_group_name "
        "FROM hr.vw_payroll_summary v LIMIT 10"
    )
    assert validate_sql_bindings(sql, grounding) is None


def test_rewrite_then_bind_across_schema():
    grounding = SchemaGrounding(
        columns_by_table={
            "hr_semantic.vw_payroll_summary": [
                "emp_fullname",
                "emp_no",
                "basic_salary",
            ],
        },
        source="test",
    )
    sql = (
        "SELECT v.employee_name FROM hr.vw_payroll_summary v "
        "WHERE v.employee_name IS NOT NULL LIMIT 10"
    )
    out = try_rewrite_unknown_columns(sql, grounding)
    assert out is not None
    assert validate_sql_bindings(out, grounding) is None


def test_order_by_select_alias_allowed():
    grounding = SchemaGrounding(
        columns_by_table={
            "hr.fct_processed_salary": ["gross_salary", "payroll_period_sk", "payroll_group_sk"],
            "hr.dim_payroll_period": ["period_end_date", "payroll_period_sk"],
            "hr.dim_payroll_group": ["payroll_group_name", "payroll_group_sk"],
        },
        source="test",
    )
    sql = """
    SELECT pg.payroll_group_name,
      date_trunc('month', pp.period_end_date::date) AS pay_month,
      SUM(COALESCE(ps.gross_salary, 0)) AS total_gross
    FROM hr.fct_processed_salary ps
    JOIN hr.dim_payroll_period pp ON pp.payroll_period_sk = ps.payroll_period_sk
    LEFT JOIN hr.dim_payroll_group pg ON pg.payroll_group_sk = ps.payroll_group_sk
    GROUP BY 1, 2
    ORDER BY pay_month, pg.payroll_group_name
    LIMIT 10
    """
    assert validate_sql_bindings(sql, grounding) is None
