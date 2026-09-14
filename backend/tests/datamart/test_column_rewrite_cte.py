"""Quick unit checks for column rewrite + CTE binding (no warehouse)."""
from app.services.ai_services.datamart.schema_broker import SchemaGrounding
from app.services.ai_services.datamart.sql.sql_binding import validate_sql_bindings
from app.services.ai_services.datamart.sql.sql_column_allowlist import try_rewrite_unknown_columns


def _payroll_grounding() -> SchemaGrounding:
    return SchemaGrounding(
        columns_by_table={
            "hr.vw_payroll_summary": [
                "emp_fullname",
                "emp_no",
                "basic_salary",
                "branch",
                "payroll_group_name",
                "payroll_frequency",
                "currency_code",
                "is_active",
            ],
        },
        source="test",
    )


def test_rewrite_qualified_payroll_name():
    g = _payroll_grounding()
    sql = (
        "SELECT p.employee_name, p.employee_no FROM hr.vw_payroll_summary p "
        "ORDER BY p.employee_name LIMIT 10;"
    )
    out = try_rewrite_unknown_columns(sql, g)
    assert out is not None
    assert "emp_fullname" in out.lower()
    assert "emp_no" in out.lower()
    assert validate_sql_bindings(out, g) is None


def test_cte_not_treated_as_table():
    g = SchemaGrounding(
        columns_by_table={
            "hr.vw_turnover": ["department_id", "employee_id"],
            "hr.vw_headcount": ["department_id", "employee_id", "is_active"],
            "hr.mart_employee_current": ["emp_section_id", "designation_department"],
        },
        source="test",
    )
    sql = """WITH sep_by_dim AS (
        SELECT department_id, COUNT(*) AS separation_count
        FROM hr.vw_turnover
        GROUP BY department_id
    )
    SELECT * FROM sep_by_dim LIMIT 10;"""
    assert validate_sql_bindings(sql, g) is None


def test_cte_alias_columns_allowed():
    g = SchemaGrounding(
        columns_by_table={
            "hr_semantic.vw_turnover": ["department_id", "employee_id"],
            "hr_semantic.vw_headcount": ["department_id", "employee_id", "is_active"],
            "hr.mart_employee_current": ["emp_section_id", "designation_department", "branch_id", "location_name"],
        },
        source="test",
    )
    sql = """WITH sep_by_dim AS (
        SELECT t.department_id, COUNT(*) AS separation_count
        FROM hr_semantic.vw_turnover t
        GROUP BY t.department_id
    ),
    hc_by_dim AS (
        SELECT h.department_id, COUNT(*) AS active_headcount
        FROM hr_semantic.vw_headcount h
        WHERE h.is_active IS TRUE
        GROUP BY h.department_id
    )
    SELECT s.separation_count, hc.active_headcount
    FROM sep_by_dim s
    JOIN hc_by_dim hc ON hc.department_id = s.department_id
    LIMIT 10;"""
    assert validate_sql_bindings(sql, g) is None


if __name__ == "__main__":
    test_rewrite_qualified_payroll_name()
    test_cte_not_treated_as_table()
    print("ok")
