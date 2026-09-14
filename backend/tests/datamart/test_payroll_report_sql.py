from app.services.ai_services.datamart.domain_sql.payroll_report_sql import build_payroll_sql_from_grounding
from app.services.ai_services.datamart.schema_broker import SchemaGrounding


def test_payroll_summary_prefers_emp_fullname_over_full_name_on_view():
    grounding = SchemaGrounding(
        columns_by_table={
            "hr_semantic.vw_payroll_summary": [
                # view exposes emp_fullname but some stale catalogs may include full_name too
                "emp_fullname",
                "full_name",
                "employee_id",
                "payroll_group_name",
                "basic_salary",
            ],
            "hr.dim_payroll_group": ["payroll_group_name", "payroll_frequency", "currency_code"],
        }
    )
    sql = build_payroll_sql_from_grounding(
        "Prepare a payroll summary report including employee name and basic salary",
        grounding,
        max_rows=10,
    )
    assert sql is not None
    assert "vw_payroll_summary" in sql
    assert ".emp_fullname" in sql
    assert ".full_name" not in sql

