"""
Dynamic employee detail-list SQL from mart_employee_current.

Covers the majority of HR roster questions (name, number, supervisor, department, etc.)
without calling the LLM.
"""
from __future__ import annotations

import re
from typing import Optional

from ..config import MAX_RESULT_ROWS
from .metric_templates import question_wants_row_detail
from ..workspace.runtime_context import mart_schema_for_hints
from ..schema_broker import SchemaGrounding

_MART = "mart_employee_current"

_NON_EMPLOYEE_DOMAIN_RE = re.compile(
    r"\b(?:leave|attendance|payroll|payslip|salary|overtime|benefit|"
    r"recruitment|recruit|hiring|candidate|candidates|applicant|pipeline|"
    r"linkedin|referral|requisition|attrition|turnover|separated|separation|tenure|time\s+off|vacation|"
    r"loan\s+deduction|epf|etf)\b",
    re.IGNORECASE,
)
# Bank / account lists must use employee_bank_detail_sql (multi-table join).
_BANK_DETAIL_RE = re.compile(
    r"\b(?:bank|account\s+number|passbook|salary\s+bank)\b",
    re.IGNORECASE,
)
# Shift lists must use employee_shift_sql (mart + dim_shift join).
_SHIFT_DETAIL_RE = re.compile(
    r"\b(?:shift|shifts|assigned\s+shift)\b",
    re.IGNORECASE,
)
# Attendance metrics / probation / designation ranking / headcount aggregates need verified SQL.
_SPECIALIZED_REPORT_RE = re.compile(
    r"\b(?:absent\s+days|present\s+days|late\s+events|probation|"
    r"rank\s+designations?)\b",
    re.IGNORECASE,
)
_HEADCOUNT_AGG_RE = re.compile(
    r"\b(?:headcount|head\s+count|employee\s+count\s+by|new\s+hires?|"
    r"separations?\s+(?:per|in)|legal\s+entit|on\s+probation|"
    r"pay\s+group|headcount\s+trend|point-in-time\s+headcount)\b",
    re.IGNORECASE,
)

# (question pattern, physical columns on mart, output alias)
_COLUMN_RULES: tuple[tuple[re.Pattern[str], tuple[str, ...], str], ...] = (
    (
        re.compile(
            r"\b(?:employee\s+number|employee\s+no|emp\s+no|emp\s+number)\b",
            re.I,
        ),
        ("emp_no", "employee_no"),
        "employee_number",
    ),
    (
        re.compile(r"\b(?:employee\s+name|emp\s+name)\b", re.I),
        ("emp_fullname", "emp_name"),
        "employee_name",
    ),
    (
        re.compile(r"\b(?:full\s+name|employee\s+full\s+name)\b", re.I),
        ("emp_fullname", "emp_name"),
        "employee_full_name",
    ),
    (
        re.compile(r"\bname\b", re.I),
        ("emp_fullname", "emp_name"),
        "employee_name",
    ),
    (
        re.compile(
            r"\b(?:supervisor|reporting\s+manager|line\s+manager|immediate\s+supervisor|"
            r"reporting\s+immediate\s+supervisor|manager\s+name)\b",
            re.I,
        ),
        ("superior_fullname",),
        "reporting_supervisor_name",
    ),
    (
        re.compile(
            r"\b(?:supervisor\s+(?:employee\s+)?number|manager\s+employee\s+number|"
            r"reporting\s+manager\s+(?:id|number)|superior\s+emp)\b",
            re.I,
        ),
        ("superior_emp_no",),
        "reporting_supervisor_employee_number",
    ),
    (
        re.compile(
            r"\b(?:employment\s+category|employee\s+category|emp\s+category)\b",
            re.I,
        ),
        ("employee_category", "employment_type"),
        "employment_category",
    ),
    (
        re.compile(r"\b(?:department|dept)\b", re.I),
        ("designation_department", "department", "department_name"),
        "department",
    ),
    (
        re.compile(r"\b(?:branch|location)\b", re.I),
        ("location_name", "branch_name", "branch"),
        "branch",
    ),
    (
        re.compile(r"\b(?:company|legal\s+entity)\b", re.I),
        ("legal_entity", "company"),
        "company",
    ),
    (
        re.compile(r"\b(?:designation|job\s+title|position|title)\b", re.I),
        ("designation", "emp_position"),
        "designation",
    ),
    (
        re.compile(r"\b(?:email|e-mail)\b", re.I),
        ("email", "work_email"),
        "email",
    ),
    (
        re.compile(r"\b(?:phone|mobile|contact)\b", re.I),
        ("phone", "mobile", "contact_number"),
        "phone",
    ),
    (
        re.compile(r"\b(?:organization\s+unit|org\s+unit)\b", re.I),
        ("emp_position",),
        "organization_unit",
    ),
)


def _qualified_mart(grounding: SchemaGrounding) -> Optional[str]:
    for q in grounding.columns_by_table:
        if q.rsplit(".", 1)[-1].lower() == _MART:
            return q
    return None


def _mart_cols(grounding: SchemaGrounding) -> list[str]:
    q = _qualified_mart(grounding)
    if not q:
        return []
    return list(grounding.columns_by_table.get(q) or [])


def _pick_col(cols: list[str], candidates: tuple[str, ...]) -> Optional[str]:
    lower = {c.lower(): c for c in cols}
    for cand in candidates:
        if cand.lower() in lower:
            return lower[cand.lower()]
    return None


def looks_like_employee_detail_list(
    question: str,
    *,
    grounding: Optional[SchemaGrounding] = None,
) -> bool:
    q = (question or "").strip()
    if not q or not question_wants_row_detail(q):
        return False
    if _BANK_DETAIL_RE.search(q):
        return False
    if _SHIFT_DETAIL_RE.search(q):
        return False
    if _SPECIALIZED_REPORT_RE.search(q):
        return False
    if _HEADCOUNT_AGG_RE.search(q):
        return False
    if _NON_EMPLOYEE_DOMAIN_RE.search(q):
        return False
    if not re.search(r"\b(?:employee|employees|staff|workforce)\b", q, re.I):
        return False
    if grounding is not None and _qualified_mart(grounding) is None:
        return False
    return True


def try_build_employee_list_sql(
    question: str,
    *,
    grounding: SchemaGrounding,
    max_rows: Optional[int] = None,
) -> Optional[str]:
    """Build SELECT from mart columns that match the question (and exist on the mart)."""
    if not looks_like_employee_detail_list(question, grounding=grounding):
        return None

    mart_q = _qualified_mart(grounding)
    if not mart_q:
        return None

    schema = mart_q.rsplit(".", 1)[0] if "." in mart_q else mart_schema_for_hints()
    cols = _mart_cols(grounding)
    if not cols:
        return None

    select_parts: list[str] = []
    seen_aliases: set[str] = set()

    for pattern, physical, alias in _COLUMN_RULES:
        if not pattern.search(question):
            continue
        col = _pick_col(cols, physical)
        if not col or alias in seen_aliases:
            continue
        select_parts.append(f"m.{col} AS {alias}")
        seen_aliases.add(alias)

    if not select_parts:
        emp_no = _pick_col(cols, ("emp_no", "employee_no"))
        emp_name = _pick_col(cols, ("emp_fullname", "emp_name"))
        if emp_no:
            select_parts.append(f"m.{emp_no} AS employee_number")
        if emp_name:
            select_parts.append(f"m.{emp_name} AS employee_name")

    if not select_parts:
        return None

    limit = max_rows if max_rows is not None else MAX_RESULT_ROWS
    where_clause = ""
    if "is_current" in {c.lower() for c in cols}:
        where_clause = "\nWHERE m.is_current IS TRUE"

    order_col = _pick_col(cols, ("emp_fullname", "emp_name", "emp_no")) or select_parts[0].split(".")[1].split()[0]
    select_sql = ",\n    ".join(select_parts)
    return f"""SELECT
    {select_sql}
FROM {schema}.{_MART} m{where_clause}
ORDER BY m.{order_col}
LIMIT {limit};"""
