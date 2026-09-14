"""SQL recovery diagnosis and planning."""
from app.services.ai_services.datamart.sql.sql_recovery import (
    RecoveryActionKind,
    SqlIssueKind,
    diagnose_sql_failure,
    plan_recovery,
)


def test_diagnose_join_type_mismatch():
    sql = "SELECT 1 FROM hr.mart_employee_current m JOIN hr.dim_shift s ON s.shift_sk = m.shift_id"
    err = "UndefinedFunction operator does not exist: text = integer"
    issue = diagnose_sql_failure(sql, err)
    assert issue.kind == SqlIssueKind.JOIN_TYPE_MISMATCH
    assert issue.repairable is True
    assert "dim_shift" in issue.extra_tables
    assert issue.llm_guidance


def test_diagnose_join_type_mismatch_without_undefinedfunction_prefix():
    sql = """
SELECT fl.leave_type, m_approver.emp_fullname
FROM hr.fact_leave_transaction fl
JOIN hr.mart_employee_current m_approver ON m_approver.employee_sk = fl.source_approved_by
"""
    err = (
        "operator does not exist: text = integer "
        "LINE 12: ON m_approver.employee_sk = fl.source_approved_by"
    )
    issue = diagnose_sql_failure(sql, err)
    assert issue.kind == SqlIssueKind.JOIN_TYPE_MISMATCH
    assert issue.repairable is True
    assert "vw_pending_leave_approvals" in issue.extra_tables
    assert "approver" in issue.llm_guidance.lower() or "emp_no" in issue.llm_guidance.lower()


def test_plan_expand_on_missing_table():
    issue = diagnose_sql_failure(
        "SELECT * FROM hr.dim_foo",
        'relation "hr.dim_foo" does not exist',
    )
    plan = plan_recovery(issue, attempt=1, max_attempts=4)
    assert plan.action == RecoveryActionKind.EXPAND_CONTEXT


def test_plan_abort_at_max():
    issue = diagnose_sql_failure(None, "No SQL in LLM response")
    plan = plan_recovery(issue, attempt=4, max_attempts=4)
    assert plan.action == RecoveryActionKind.ABORT
