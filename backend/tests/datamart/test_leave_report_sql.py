"""Leave detail report SQL template."""
from app.services.ai_services.datamart.domain_sql.leave_report_sql import (
    looks_like_leave_detail_report,
    try_build_leave_detail_report_sql,
)
from app.services.ai_services.datamart.schema_broker import SchemaGrounding
from app.services.ai_services.datamart.sql.sql_answer_adequacy import check_sql_answers_question
from app.services.ai_services.datamart.domain_sql.workforce_sql_template import looks_like_workforce_report

LEAVE_Q = (
    "Generate a report of employees and their leave details by combining employee "
    "and leave transaction information. Include employee name, employee ID, branch, "
    "leave type, leave start date, leave end date, total leave days, and leave status. "
    "Display only approved leave requests"
)

WORKFORCE_MART_SQL = """
SELECT m.emp_fullname AS employee_name, m.emp_no AS employee_no
FROM hr.mart_employee_current m
LIMIT 500
"""


def _transaction_grounding() -> SchemaGrounding:
    return SchemaGrounding(
        columns_by_table={
            "hr.dim_employee": [
                "employee_id",
                "employee_no",
                "full_name",
                "branch_name",
                "is_current",
            ],
            "hr.fact_leave_transaction": [
                "employee_id",
                "leave_type_id",
                "leave_start_date",
                "leave_end_date",
                "leave_days",
                "leave_status_name",
            ],
            "hr.dim_leave_type": ["leave_type_id", "leave_type_name"],
        },
        source="test",
    )


def test_leave_question_detected():
    assert looks_like_leave_detail_report(LEAVE_Q)


def test_leave_question_not_workforce_template():
    assert not looks_like_workforce_report(LEAVE_Q)


def test_leave_template_joins_transaction_tables():
    sql = try_build_leave_detail_report_sql(
        LEAVE_Q,
        grounding=_transaction_grounding(),
    )
    assert sql is not None
    assert "fact_leave_transaction" in sql
    assert "dim_leave_type" in sql
    assert "mart_employee_current" not in sql


def test_adequacy_rejects_workforce_mart_for_leave_question():
    err = check_sql_answers_question(question=LEAVE_Q, sql=WORKFORCE_MART_SQL)
    assert err is not None
    assert "leave" in err.lower()
