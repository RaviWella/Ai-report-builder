"""Approver join repairs for leave pending approval SQL."""
from app.services.ai_services.datamart.sql.sql_exec_repairs import (
    repair_approver_join_keys,
    repair_generic_join_cast_from_error,
)


def test_repair_approver_employee_sk_to_source_approved_by():
    sql = """
SELECT fl.leave_type, m_approver.emp_fullname
FROM hr.fact_leave_transaction fl
JOIN hr.mart_employee_current m_approver ON m_approver.employee_sk = fl.source_approved_by
LIMIT 500
"""
    err = (
        "operator does not exist: text = integer "
        "LINE 4: ON m_approver.employee_sk = fl.source_approved_by"
    )
    fixed = repair_approver_join_keys(sql, err)
    assert fixed is not None
    assert "m_approver.emp_no::text = fl.source_approved_by::text" in fixed
    assert "employee_sk" not in fixed


def test_repair_generic_join_cast_from_error_line():
    sql = """
SELECT 1
FROM hr.fact_leave_transaction fl
JOIN hr.mart_employee_current m ON m.employee_sk = fl.source_approver_emp_id
"""
    err = "operator does not exist: integer = text LINE 3: ON m.employee_sk = fl.source_approver_emp_id"
    fixed = repair_generic_join_cast_from_error(sql, err)
    assert fixed is not None
    assert "m.employee_sk::text = fl.source_approver_emp_id::text" in fixed
