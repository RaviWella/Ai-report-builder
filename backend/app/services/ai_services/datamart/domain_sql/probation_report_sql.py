"""
Grounded probation / employee-status SQL (mart_employee_current only).

Used when binding fails or the LLM invents dim_employee columns like manager_emp_no.
"""
from __future__ import annotations

import re
from typing import Optional

from ..config import MAX_RESULT_ROWS
from .leave_report_sql import (
    _cols_for_short,
    _pick_col,
    _pick_employee_table,
    _schema_from_grounding,
)
from .metric_templates import question_wants_row_detail
from ..schema_broker import SchemaGrounding

_PROBATION_RE = re.compile(r"\bprobation\b", re.IGNORECASE)


def looks_like_probation_employee_report(question: str) -> bool:
    q = (question or "").strip()
    if not q or not _PROBATION_RE.search(q):
        return False
    if not question_wants_row_detail(q):
        return False
    return bool(
        re.search(
            r"\b(?:employee|staff|name|designation|manager|grade|active|completion|"
            r"due\s+date|timeline|exceeded)\b",
            q,
            re.I,
        )
    )


def build_probation_report_sql_from_grounding(
    question: str,
    grounding: SchemaGrounding,
    *,
    max_rows: Optional[int] = None,
) -> Optional[str]:
    if not grounding.columns_by_table:
        return None

    emp_short = _pick_employee_table(grounding)
    if not emp_short:
        return None

    cols = _cols_for_short(grounding, emp_short)
    if not cols:
        return None

    schema = _schema_from_grounding(grounding)
    limit = max_rows if max_rows is not None else MAX_RESULT_ROWS
    alias = "m"
    q = question.lower()

    select_parts: list[str] = []
    name_col = _pick_col(cols, ("emp_fullname", "full_name", "employee_name", "emp_name"))
    if name_col:
        select_parts.append(f"    {alias}.{name_col} AS employee_name")
    id_col = _pick_col(cols, ("emp_no", "employee_no", "employee_id"))
    if id_col:
        select_parts.append(f"    {alias}.{id_col} AS employee_id")
    mgr_name = _pick_col(cols, ("superior_fullname", "manager_name", "reporting_manager_name"))
    if mgr_name:
        select_parts.append(f"    {alias}.{mgr_name} AS reporting_manager")
    mgr_id = _pick_col(cols, ("superior_emp_no", "manager_emp_no", "superior_source_emp_id"))
    if mgr_id:
        select_parts.append(f"    {alias}.{mgr_id} AS reporting_manager_id")
    desig = _pick_col(cols, ("designation", "designation_name", "job_title", "emp_position"))
    if desig:
        select_parts.append(f"    {alias}.{desig} AS designation")
    grade = _pick_col(cols, ("grade_name", "grade", "emp_grade"))
    if grade:
        select_parts.append(f"    {alias}.{grade} AS grade")
    due = _pick_col(cols, ("probation_due_date", "probation_end_date"))
    if due:
        select_parts.append(f"    {alias}.{due} AS probation_due_date")
    status = _pick_col(
        cols,
        (
            "probation_status",
            "probation_completion_status",
            "probation_completed_date",
            "latest_probation_start_date",
        ),
    )
    if status:
        select_parts.append(f"    {alias}.{status} AS probation_status")

    if len(select_parts) < 2:
        return None

    where_parts: list[str] = []
    if re.search(r"\bactive\b", q) and _pick_col(cols, ("is_active", "employment_status")):
        active_col = _pick_col(cols, ("is_active",))
        if active_col:
            where_parts.append(f"{alias}.{active_col} IS TRUE")
        else:
            status_col = _pick_col(cols, ("employment_status",))
            if status_col:
                where_parts.append(f"LOWER({alias}.{status_col}) = 'active'")

    if due and re.search(r"\bexceed|overdue|past\b", q):
        where_parts.append(f"{alias}.{due} < CURRENT_DATE")

    where_sql = ""
    if where_parts:
        where_sql = "\nWHERE " + "\n  AND ".join(where_parts)

    return (
        "SELECT\n"
        + ",\n".join(select_parts)
        + f"\nFROM {schema}.{emp_short} {alias}"
        + where_sql
        + f"\nORDER BY {alias}.{due or name_col or id_col} NULLS LAST\n"
        + f"LIMIT {limit};"
    )


def try_build_probation_report_sql(
    question: str,
    grounding: Optional[SchemaGrounding] = None,
) -> Optional[str]:
    if not looks_like_probation_employee_report(question):
        return None
    if grounding is not None:
        return build_probation_report_sql_from_grounding(question, grounding)
    return None
