"""
Fast final gate: does SQL project the report columns the user asked for?

Binding / schema / domain tables are validated earlier; this step only checks
SELECT output shape and named attributes (no ReportSpec re-validation, no catalog links).
"""
from __future__ import annotations

import re
from typing import Optional

import sqlglot
from sqlglot import exp

from ..llm.llm_response import is_non_executable_sql
from ..domain_sql.metric_templates import is_scalar_aggregate_sql, question_wants_row_detail

_REQUESTED_FIELDS: list[tuple[str, re.Pattern[str], tuple[str, ...]]] = [
    ("employee name", re.compile(r"\bemployee\s+name\b", re.I), ("full_name", "emp_fullname", "employee_name", "emp_name")),
    ("employee id", re.compile(r"\bemployee\s+(?:id|no|number)\b", re.I), ("employee_id", "emp_id", "employee_no", "emp_no")),
    ("company", re.compile(r"\bcompany\b", re.I), ("company", "legal_entity", "org_company", "company_name")),
    ("branch", re.compile(r"\bbranch\b", re.I), ("branch", "branch_name", "branch_id", "location_name")),
    ("department", re.compile(r"\bdepartment\b", re.I), ("department", "dept", "department_name", "designation_department")),
    ("organization unit", re.compile(r"\borganization\s+unit\b", re.I), ("org_unit", "organization_unit", "unit_name", "emp_position")),
    ("designation", re.compile(r"\bdesignation\b", re.I), ("designation", "job_title", "title", "designation_id")),
    ("reporting manager", re.compile(r"\breporting\s+manager\b", re.I), ("manager", "reporting_manager", "superior_emp_no", "superior_fullname", "supervisor")),
    ("salary", re.compile(r"\b(?:basic\s+)?salary\b", re.I), ("salary", "basic_salary", "gross_pay", "net_pay")),
    ("payroll group name", re.compile(r"\bpayroll\s+group\b", re.I), ("payroll_group_name", "payroll_group")),
    ("pay frequency", re.compile(r"\bpay\s+frequency\b", re.I), ("payroll_frequency", "pay_frequency")),
    ("currency code", re.compile(r"\bcurrency(?:\s+code)?\b", re.I), ("currency_code",)),
    ("job title", re.compile(r"\bjob\s+title\b", re.I), ("job_title", "designation", "title")),
    ("leave type", re.compile(r"\bleave\s+type\b", re.I), ("leave_type_name", "leave_type")),
    ("leave start date", re.compile(r"\bleave\s+start\s+date\b", re.I), ("leave_start_date", "leave_start", "period_label")),
    ("leave end date", re.compile(r"\bleave\s+end\s+date\b", re.I), ("leave_end_date", "leave_end", "period_label")),
    ("leave days", re.compile(r"\b(?:total\s+)?leave\s+days\b", re.I), ("leave_days", "total_leave_days", "days_approved", "days_taken")),
    ("leave status", re.compile(r"\bleave\s+status\b", re.I), ("leave_status_name", "leave_status")),
    ("bank details", re.compile(r"\bbank\s+details?\b", re.I), ("bank_name", "bank_code", "account_number", "bank_passbook_name")),
    ("bank name", re.compile(r"\bbank\s+name\b", re.I), ("bank_name", "bank_passbook_name")),
    ("bank code", re.compile(r"\bbank\s+code\b", re.I), ("bank_code",)),
    ("employment category", re.compile(r"\bemployment\s+category\b", re.I), ("employment_category", "employee_category")),
    ("shift name", re.compile(r"\b(?:assigned\s+)?shift\s+name\b", re.I), ("shift_name",)),
    ("shift", re.compile(r"\bshift\b", re.I), ("shift_name", "assigned_shift_name")),
]

_MAX_MISSING_LABELS = 2


def _requested_labels(question: str) -> list[str]:
    return [label for label, pattern, _ in _REQUESTED_FIELDS if pattern.search(question)]


def _count_select_columns(sql: str) -> int:
    try:
        tree = sqlglot.parse_one(sql, dialect="postgres")
    except Exception:  # noqa: BLE001
        return 0
    select = tree.find(exp.Select)
    if not select:
        return 0
    return sum(1 for e in select.expressions if not isinstance(e, exp.Star))



def _missing_output_labels(question: str, text_blob: str) -> list[str]:
    missing: list[str] = []
    blob_l = (text_blob or "").lower()
    for label, pattern, col_frags in _REQUESTED_FIELDS:
        if not pattern.search(question):
            continue
        if not any(frag in blob_l for frag in col_frags):
            missing.append(label)
    return missing


def _missing_output_labels_from_sql(question: str, sql_l: str) -> list[str]:
    return _missing_output_labels(question, sql_l)


def score_sql_output_columns(question: str, sql: Optional[str]) -> int:
    """Higher score = better match to requested report columns."""
    if is_non_executable_sql(sql):
        return -100
    q = (question or "").strip()
    sql_l = (sql or "").lower()
    requested = _requested_labels(q)
    score = 0
    for label in requested:
        for field_label, pattern, col_frags in _REQUESTED_FIELDS:
            if field_label == label and any(frag in sql_l for frag in col_frags):
                score += 10
                break
    missing = _missing_output_labels_from_sql(q, sql_l)
    score -= 15 * len(missing)
    if question_wants_row_detail(q):
        if is_scalar_aggregate_sql(sql):
            score -= 50
        n_sel = _count_select_columns(sql)
        if n_sel > 0:
            score += min(n_sel, 12)
        if requested and n_sel > 0 and n_sel < min(len(requested), 4):
            score -= 10
    return score


def pick_better_sql_for_question(
    question: str,
    sql_a: Optional[str],
    sql_b: Optional[str],
) -> tuple[Optional[str], str]:
    """Return (chosen_sql, reason_tag)."""
    sa = score_sql_output_columns(question, sql_a)
    sb = score_sql_output_columns(question, sql_b)
    if sb > sa:
        return sql_b, "regen_candidate"
    if sa > sb:
        return sql_a, "original"
    if not check_sql_output_columns(question, sql_b):
        return sql_b, "regen_candidate"
    return sql_a, "original"


def check_sql_output_columns(question: str, sql: Optional[str]) -> Optional[str]:
    """Return user-facing error if report output columns do not match the question."""
    if is_non_executable_sql(sql):
        return "No SQL was produced for this question."

    q = (question or "").strip()
    sql_l = (sql or "").lower()
    wants_detail = question_wants_row_detail(q)

    if wants_detail and is_scalar_aggregate_sql(sql):
        names = _requested_labels(q)[:4]
        hint = ", ".join(names) if names else "the requested attributes"
        return (
            f"This question asks for a detailed report ({hint}), but the SQL only "
            "returns a single aggregate or one column."
        )

    missing = _missing_output_labels_from_sql(q, sql_l)
    if len(missing) > _MAX_MISSING_LABELS:
        return (
            "SQL is missing report columns you asked for: "
            + ", ".join(missing[:6])
            + "."
        )

    if wants_detail:
        requested = _requested_labels(q)
        if requested:
            n_sel = _count_select_columns(sql)
            min_cols = min(4, max(2, len(requested)))
            if n_sel > 0 and n_sel < min_cols and len(missing) >= 2:
                return (
                    f"The question asks for about {len(requested)} attributes, but SQL only "
                    f"projects {n_sel} column(s)."
                )

    return None


def check_sql_answers_question(
    *,
    question: str,
    sql: Optional[str],
    schema_links: Optional[list] = None,
    report_spec: Optional[object] = None,
) -> Optional[str]:
    """Backward-compatible alias — output columns only (fast)."""
    _ = schema_links, report_spec
    return check_sql_output_columns(question, sql)


def check_result_columns_match_question(
    question: str,
    columns: list[str],
    *,
    row_count: int = 0,
) -> Optional[str]:
    """
    After warehouse execution: do returned column names match what the user asked?

    This validates the **actual result set**, not SQL text or broker metadata.
    """
    if not columns:
        return "Query returned no columns (execution failed or empty result)."

    q = (question or "").strip()
    cols_blob = " ".join(str(c) for c in columns)
    wants_detail = question_wants_row_detail(q)

    if wants_detail and len(columns) == 1 and row_count <= 1:
        low = cols_blob.lower()
        if any(
            tok in low
            for tok in ("count", "total", "sum", "avg", "average", "rate", "ratio")
        ):
            names = _requested_labels(q)[:4]
            hint = ", ".join(names) if names else "the requested attributes"
            return (
                f"Question asks for a detail report ({hint}), but the result is a "
                f"single aggregate column ({columns[0]})."
            )

    missing = _missing_output_labels(q, cols_blob)
    if len(missing) > _MAX_MISSING_LABELS:
        return (
            "Result is missing columns the user asked for: "
            + ", ".join(missing[:6])
            + f". Got: {', '.join(columns[:12])}."
        )

    if wants_detail:
        requested = _requested_labels(q)
        if requested and len(columns) < min(4, max(2, len(requested))) and len(missing) >= 2:
            return (
                f"Question asks for about {len(requested)} attributes, but the result "
                f"only has {len(columns)} column(s): {', '.join(columns[:8])}."
            )

    return None


def score_result_columns(question: str, columns: list[str]) -> int:
    """Score actual warehouse result columns against the question."""
    if not columns:
        return -100
    blob = " ".join(str(c) for c in columns).lower()
    score = 0
    for label in _requested_labels(question):
        for field_label, _pattern, col_frags in _REQUESTED_FIELDS:
            if field_label == label and any(frag in blob for frag in col_frags):
                score += 10
                break
    score -= 15 * len(_missing_output_labels(question, blob))
    score += min(len(columns), 12)
    return score
