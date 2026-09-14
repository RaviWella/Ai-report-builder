"""Column value peek and zero-row filter repairs."""
from unittest.mock import patch

from app.services.ai_services.datamart.semantic.column_value_peek import (
    analyze_zero_row_filters,
    extract_string_equality_literals,
    is_categorical_column,
)
from app.services.ai_services.datamart.sql.sql_exec_repairs import (
    repair_filter_literal_case,
    repair_redundant_prefiltered_view_filters,
    try_repair_zero_row_sql,
)


def test_is_categorical_column():
    assert is_categorical_column("approval_status") is True
    assert is_categorical_column("leave_type_name") is False
    assert is_categorical_column("emp_fullname") is False


def test_extract_string_equality_literals():
    sql = "SELECT 1 FROM hr_semantic.vw_pending_leave_approvals p WHERE p.approval_status = 'Pending'"
    lits = extract_string_equality_literals(sql)
    assert len(lits) == 1
    assert lits[0].column == "approval_status"
    assert lits[0].literal == "Pending"


def test_repair_redundant_pending_leave_filter():
    sql = """
SELECT p.leave_type
FROM hr_semantic.vw_pending_leave_approvals p
WHERE p.approval_status = 'Pending'
ORDER BY p.leave_apply_date DESC
LIMIT 500
"""
    fixed = repair_redundant_prefiltered_view_filters(sql)
    assert fixed is not None
    assert "approval_status" not in fixed
    assert "WHERE" not in fixed.upper() or "ORDER BY" in fixed


def test_repair_filter_literal_case():
    sql = "SELECT 1 FROM t WHERE t.approval_status = 'Pending'"
    fixed = repair_filter_literal_case(sql, "approval_status", "Pending", ["pending"])
    assert fixed is not None
    assert "= 'pending'" in fixed


def test_analyze_zero_row_filters_detects_mismatch():
    sql = """
SELECT p.leave_type FROM hr_semantic.vw_pending_leave_approvals p
WHERE p.approval_status = 'Pending'
"""
    cols = {"hr_semantic.vw_pending_leave_approvals": ["approval_status", "leave_type"]}
    with patch(
        "app.services.ai_services.datamart.semantic.column_value_peek.peek_distinct_values",
        return_value=["pending"],
    ):
        analysis = analyze_zero_row_filters(sql, cols)
    assert analysis is not None
    assert analysis.has_actionable_mismatch


def test_try_repair_zero_row_sql_removes_redundant_filter():
    sql = """
SELECT p.leave_type FROM hr_semantic.vw_pending_leave_approvals p
WHERE p.approval_status = 'Pending'
LIMIT 500
"""
    cols = {"hr_semantic.vw_pending_leave_approvals": ["approval_status", "leave_type"]}
    with patch(
        "app.services.ai_services.datamart.semantic.column_value_peek.peek_distinct_values",
        return_value=["pending"],
    ):
        analysis = analyze_zero_row_filters(sql, cols)
    fixed = try_repair_zero_row_sql(sql, analysis)
    assert fixed is not None
    assert "approval_status" not in fixed
