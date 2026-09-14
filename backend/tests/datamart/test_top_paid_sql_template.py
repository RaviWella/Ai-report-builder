"""Top-paid report SQL template."""
from app.services.ai_services.datamart.domain_sql.workforce_sql_template import (
    looks_like_top_paid_report,
    try_build_top_paid_report_sql,
)

TOP_PAID_Q = "Show me the top 10 highest paid employees and their job titles"


def test_top_paid_detected():
    assert looks_like_top_paid_report(TOP_PAID_Q)


def test_top_paid_template_uses_mart_designation_column():
    sql = try_build_top_paid_report_sql(TOP_PAID_Q)
    assert sql is not None
    assert "mart_employee_current" in sql
    assert "m.designation AS job_title" in sql
    assert "designation_name" not in sql
    assert "ORDER BY m.basic_salary DESC" in sql
    assert "LIMIT 10" in sql
