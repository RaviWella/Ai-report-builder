"""Workforce report SQL template fallback."""
from __future__ import annotations

from app.services.ai_services.datamart.llm.llm_response import is_non_executable_sql, normalize_executable_sql
from app.services.ai_services.datamart.domain_sql.workforce_sql_template import (
    build_workforce_report_sql,
    looks_like_workforce_report,
    try_build_workforce_report_sql,
)

WORKFORCE_Q = (
    "Generate a workforce report by combining employee and organization data. "
    "Include employee name, employee ID, company, branch, department, "
    "organization unit, designation ID, and reporting manager employee ID"
)


def test_non_executable_sql_detects_none():
    assert is_non_executable_sql("NONE")
    assert is_non_executable_sql("  none  ")
    assert normalize_executable_sql("NONE") is None
    assert not is_non_executable_sql("SELECT 1")


def test_workforce_report_detected():
    assert looks_like_workforce_report(WORKFORCE_Q)


def test_workforce_template_uses_mart():
    sql = try_build_workforce_report_sql(WORKFORCE_Q)
    assert sql is not None
    assert "mart_employee_current" in sql
    assert "emp_fullname" in sql
    assert "designation_department" in sql
    assert "superior_emp_no" in sql
    assert "designation_id" in sql


def test_workforce_template_without_designation_id():
    q = "Generate a workforce report with employee name, company, and branch"
    sql = build_workforce_report_sql(q)
    assert "designation_id" not in sql
    assert "job_title" in sql or "designation AS" in sql
