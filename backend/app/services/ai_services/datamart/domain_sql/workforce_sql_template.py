"""
Deterministic workforce report SQL (mart_employee_current).

Used when the LLM returns SQL:NONE or omits SQL for multi-column workforce questions.
"""
from __future__ import annotations

import re
from typing import Optional

from ..config import MAX_RESULT_ROWS
from .metric_templates import question_wants_row_detail
from ..workspace.runtime_context import mart_schema_for_hints

_WORKFORCE_REPORT_RE = re.compile(
    r"\b("
    r"workforce\s+report|workforce\s+data|employee\s+master|"
    r"organization\s+data|org\s+chart|headcount\s+report|employee\s+listing"
    r")\b",
    re.IGNORECASE,
)

# Other HR domains — never use the workforce mart template for these.
_NON_WORKFORCE_DOMAIN_RE = re.compile(
    r"\b(?:leave|attendance|payroll|salary|payslip|overtime|benefit|"
    r"recruitment|applicant|attrition|turnover|time\s+off|vacation)\b",
    re.IGNORECASE,
)


def looks_like_workforce_report(question: str) -> bool:
    q = (question or "").strip()
    if not q or not question_wants_row_detail(q):
        return False
    if _NON_WORKFORCE_DOMAIN_RE.search(q):
        return False
    if re.search(r"\bcombining\b", q, re.I) and _NON_WORKFORCE_DOMAIN_RE.search(q):
        return False
    if _WORKFORCE_REPORT_RE.search(q):
        return True
    hints = len(
        re.findall(
            r"\b(?:employee\s+name|employee\s+id|company|branch|department|"
            r"designation|manager|organization\s+unit)\b",
            q,
            re.IGNORECASE,
        )
    )
    return hints >= 4


def build_workforce_report_sql(
    question: str,
    *,
    max_rows: Optional[int] = None,
) -> str:
    """
    Single-table workforce listing from ``mart_employee_current`` (denormalized mart).

    Joins ``dim_employee`` only for ``designation_id`` when the question asks for it.
    """
    schema = mart_schema_for_hints()
    limit = max_rows if max_rows is not None else MAX_RESULT_ROWS
    q = question.lower()
    want_designation_id = bool(
        re.search(r"\bdesignation\s+id\b", q) or re.search(r"\bdesignation_id\b", q)
    )
    designation_col = (
        ",\n    d.designation_id AS designation_id"
        if want_designation_id
        else ",\n    m.designation AS job_title"
    )
    join_dim = (
        f"\nJOIN {schema}.dim_employee d\n"
        f"  ON d.employee_sk = m.employee_sk\n"
        f" AND d.is_current IS TRUE"
        if want_designation_id
        else ""
    )
    return f"""SELECT
    m.emp_fullname AS employee_name,
    m.emp_no AS employee_no,
    m.legal_entity AS company,
    m.location_name AS branch,
    m.designation_department AS department,
    m.emp_position AS organization_unit{designation_col},
    m.superior_emp_no AS reporting_manager_employee_id,
    m.superior_fullname AS reporting_manager_name
FROM {schema}.mart_employee_current m{join_dim}
ORDER BY m.emp_fullname
LIMIT {limit};"""


def try_build_workforce_report_sql(question: str) -> Optional[str]:
    if not looks_like_workforce_report(question):
        return None
    return build_workforce_report_sql(question)


_TOP_PAID_RE = re.compile(
    r"\b(?:top|first|highest)\s+(\d+)\b.*\b(?:paid|salary|salaries|earning|compensation)\b"
    r"|\b(?:top|first)\s+(\d+)\s+(?:highest\s+)?(?:paid|salary)\b",
    re.IGNORECASE,
)


_TOP_PAID_EXCLUDE_RE = re.compile(
    r"\b(?:top\s+\d+\s*%|quartile|percentile|cost\s+drivers?|combined\s+basic)\b",
    re.IGNORECASE,
)


def looks_like_top_paid_report(question: str) -> bool:
    q = (question or "").strip()
    if not q:
        return False
    if _TOP_PAID_EXCLUDE_RE.search(q):
        return False
    if not _TOP_PAID_RE.search(q) and not (
        re.search(r"\btop\b", q, re.I)
        and re.search(r"\b(?:paid|salary|salaries)\b", q, re.I)
        and re.search(r"\b\d+\b", q)
    ):
        return False
    return bool(re.search(r"\b(?:employee|staff|worker)\b", q, re.I)) or question_wants_row_detail(q)


def build_top_paid_report_sql(question: str) -> str:
    """Top-N employees by basic_salary on mart_employee_current (denormalized)."""
    schema = mart_schema_for_hints()
    m = re.search(r"\b(?:top|first|highest)\s+(\d+)\b", question, re.I) or re.search(
        r"\b(\d+)\s+(?:highest|top)\b", question, re.I
    )
    limit = int(m.group(1)) if m else 10
    want_title = bool(
        re.search(r"\b(?:job\s+title|job\s+titles|title|designation|role|position)\b", question, re.I)
    )
    want_branch = bool(re.search(r"\bbranch\b", question, re.I))
    want_department = bool(re.search(r"\bdepartment\b", question, re.I))
    want_pay_group = bool(re.search(r"\bpay(?:roll)?\s+group\b", question, re.I))
    title_line = "    m.designation AS job_title,\n" if want_title else ""
    branch_line = "    m.location_name AS branch,\n" if want_branch else ""
    dept_line = "    m.designation_department AS department,\n" if want_department else ""
    pay_group_line = "    m.payroll_group AS pay_group,\n" if want_pay_group else ""
    return f"""SELECT
    m.emp_fullname AS employee_name,
{branch_line}{dept_line}{pay_group_line}{title_line}    m.basic_salary
FROM {schema}.mart_employee_current m
WHERE m.basic_salary IS NOT NULL
ORDER BY m.basic_salary DESC NULLS LAST
LIMIT {limit};"""


def try_build_top_paid_report_sql(question: str) -> Optional[str]:
    if not looks_like_top_paid_report(question):
        return None
    return build_top_paid_report_sql(question)
