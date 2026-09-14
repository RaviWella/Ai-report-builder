"""SQL must answer the user question before execution."""
from app.services.ai_services.datamart.sql.sql_answer_adequacy import check_sql_answers_question


WORKFORCE_Q = (
    "Generate a workforce report by combining employee and organization data. "
    "Include employee name, employee ID, company, branch, department, "
    "organization unit, designation ID, and reporting manager employee ID"
)

COUNT_SQL = (
    "SELECT COUNT(DISTINCT employee_id) AS employee_count "
    "FROM hr.dim_employee WHERE dim_employee.is_current IS TRUE"
)

DETAIL_SQL = """
SELECT e.full_name, e.employee_id, c.company_name, b.branch_name,
       d.department_name, ou.unit_name, e.designation_id, e.reporting_manager_id
FROM hr_semantic.dim_employee e
JOIN hr_semantic.dim_company c ON e.company_id = c.company_id
JOIN hr_semantic.dim_branch b ON e.branch_id = b.branch_id
LIMIT 500
"""


def test_count_sql_rejected_for_workforce_report():
    err = check_sql_answers_question(question=WORKFORCE_Q, sql=COUNT_SQL)
    assert err is not None
    assert "aggregate" in err.lower() or "one column" in err.lower()


def test_detail_sql_accepted_for_workforce_report():
    err = check_sql_answers_question(question=WORKFORCE_Q, sql=DETAIL_SQL)
    assert err is None


def test_leave_template_sql_passes_adequacy():
    from app.services.ai_services.datamart.domain_sql.leave_report_sql import try_build_leave_detail_report_sql
    from app.services.ai_services.datamart.schema_broker import SchemaGrounding

    leave_q = (
        "Generate a report combining employee and leave transaction information. "
        "Include employee name, leave type, leave start date, leave end date, "
        "total leave days, and leave status. Display only approved leave requests"
    )
    g = SchemaGrounding(
        columns_by_table={
            "hr.fact_leave_balance": [
                "source_emp_id",
                "leave_type_name",
                "period_label",
                "days_approved",
            ],
            "hr.dim_employee": [
                "employee_id",
                "employee_no",
                "full_name",
                "branch_name",
                "is_current",
            ],
        },
        source="test",
    )
    sql = try_build_leave_detail_report_sql(leave_q, grounding=g)
    assert sql is not None
    err = check_sql_answers_question(question=leave_q, sql=sql)
    assert err is None
