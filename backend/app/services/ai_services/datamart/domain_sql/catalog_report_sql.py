"""
Deterministic report SQL from semantic views (turnover / headcount).

Avoids LLM inventing columns such as ``attrition_rate`` that are not physical columns.
"""
from __future__ import annotations

import re
from typing import Optional

from ..config import MAX_RESULT_ROWS
from ..workspace.runtime_context import mart_schema_for_hints

_ATTRITION_RATE_RE = re.compile(
    r"\b(?:attrition|turnover)\s+rate\b|\b(?:highest|lowest|top)\b.*\b(?:attrition|turnover)\b",
    re.IGNORECASE,
)
_BY_DEPARTMENT_RE = re.compile(
    r"\b(?:department|dept|division)\b",
    re.IGNORECASE,
)
_BY_BRANCH_RE = re.compile(
    r"\b(?:branch|location|site)\b",
    re.IGNORECASE,
)
_HEADCOUNT_BREAKDOWN_RE = re.compile(
    r"\b(?:head\s*count|headcount|employee\s+count|number\s+of\s+(?:active\s+)?employees)\b",
    re.IGNORECASE,
)
_RANKING_RE = re.compile(
    r"\b(?:highest|lowest|top|rank|compare|which)\b",
    re.IGNORECASE,
)


def _semantic_view_schema() -> str:
    from ..workspace.runtime_context import get_datamart_context

    ctx = get_datamart_context()
    if ctx is not None and ctx.is_tenant_etl:
        return ctx.primary_schema
    return mart_schema_for_hints()


def looks_like_attrition_rate_report(question: str) -> bool:
    q = (question or "").strip()
    if not q:
        return False
    if not _ATTRITION_RATE_RE.search(q):
        return False
    return bool(
        _BY_DEPARTMENT_RE.search(q)
        or _BY_BRANCH_RE.search(q)
        or _RANKING_RE.search(q)
    )


def _parse_limit(question: str, default: int = 50) -> int:
    m = re.search(r"\b(?:top|first)\s+(\d+)\b", question, re.I)
    if m:
        return min(int(m.group(1)), MAX_RESULT_ROWS)
    return min(default, MAX_RESULT_ROWS)


def build_attrition_rate_by_department_sql(
    question: str,
    *,
    max_rows: Optional[int] = None,
) -> str:
    """Separations / active headcount by department from semantic views."""
    semantic = _semantic_view_schema()
    mart = mart_schema_for_hints()
    limit = max_rows if max_rows is not None else _parse_limit(question)
    return f"""WITH sep_by_dim AS (
    SELECT
        t.department_id,
        COUNT(DISTINCT t.employee_id) AS separation_count
    FROM {semantic}.vw_turnover t
    WHERE t.employee_id IS NOT NULL
      AND t.department_id IS NOT NULL
    GROUP BY t.department_id
),
hc_by_dim AS (
    SELECT
        h.department_id,
        COUNT(DISTINCT h.employee_id) AS active_headcount
    FROM {semantic}.vw_headcount h
    WHERE h.is_active IS TRUE
      AND h.employee_id IS NOT NULL
      AND h.department_id IS NOT NULL
    GROUP BY h.department_id
),
dept_label AS (
    SELECT DISTINCT
        m.emp_section_id AS department_id,
        m.designation_department AS department
    FROM {mart}.mart_employee_current m
    WHERE m.emp_section_id IS NOT NULL
      AND m.designation_department IS NOT NULL
)
SELECT
    COALESCE(d.department, 'Dept ' || s.department_id::text) AS department,
    s.separation_count,
    hc.active_headcount,
    ROUND(100.0 * s.separation_count / NULLIF(hc.active_headcount, 0), 2) AS attrition_rate_pct
FROM sep_by_dim s
INNER JOIN hc_by_dim hc ON hc.department_id = s.department_id
LEFT JOIN dept_label d ON d.department_id = s.department_id
ORDER BY attrition_rate_pct DESC NULLS LAST
LIMIT {limit};"""


def build_attrition_rate_by_branch_sql(
    question: str,
    *,
    max_rows: Optional[int] = None,
) -> str:
    semantic = _semantic_view_schema()
    mart = mart_schema_for_hints()
    limit = max_rows if max_rows is not None else _parse_limit(question)
    return f"""WITH sep_by_dim AS (
    SELECT
        t.branch_id,
        COUNT(DISTINCT t.employee_id) AS separation_count
    FROM {semantic}.vw_turnover t
    WHERE t.employee_id IS NOT NULL
      AND t.branch_id IS NOT NULL
    GROUP BY t.branch_id
),
hc_by_dim AS (
    SELECT
        h.branch_id,
        COUNT(DISTINCT h.employee_id) AS active_headcount
    FROM {semantic}.vw_headcount h
    WHERE h.is_active IS TRUE
      AND h.employee_id IS NOT NULL
      AND h.branch_id IS NOT NULL
    GROUP BY h.branch_id
),
branch_label AS (
    SELECT DISTINCT
        m.branch_id,
        m.location_name AS branch
    FROM {mart}.mart_employee_current m
    WHERE m.branch_id IS NOT NULL
      AND m.location_name IS NOT NULL
)
SELECT
    COALESCE(b.branch, 'Branch ' || s.branch_id::text) AS branch,
    s.separation_count,
    hc.active_headcount,
    ROUND(100.0 * s.separation_count / NULLIF(hc.active_headcount, 0), 2) AS attrition_rate_pct
FROM sep_by_dim s
INNER JOIN hc_by_dim hc ON hc.branch_id = s.branch_id
LEFT JOIN branch_label b ON b.branch_id = s.branch_id
ORDER BY attrition_rate_pct DESC NULLS LAST
LIMIT {limit};"""


def try_build_attrition_rate_report_sql(question: str) -> Optional[str]:
    if not looks_like_attrition_rate_report(question):
        return None
    if _BY_BRANCH_RE.search(question or "") and not _BY_DEPARTMENT_RE.search(question or ""):
        return build_attrition_rate_by_branch_sql(question)
    return build_attrition_rate_by_department_sql(question)


def looks_like_headcount_breakdown(question: str) -> bool:
    """Active employee counts grouped by department or branch (not attrition rate)."""
    q = (question or "").strip()
    if not q or _ATTRITION_RATE_RE.search(q):
        return False
    if not _HEADCOUNT_BREAKDOWN_RE.search(q):
        return False
    return bool(_BY_DEPARTMENT_RE.search(q) or _BY_BRANCH_RE.search(q))


def build_headcount_by_department_sql(
    question: str,
    *,
    max_rows: Optional[int] = None,
) -> str:
    mart = mart_schema_for_hints()
    limit = max_rows if max_rows is not None else _parse_limit(question)
    return f"""SELECT
    e.designation_department AS department,
    COUNT(DISTINCT e.employee_sk) AS headcount
FROM {mart}.mart_employee_current e
WHERE COALESCE(e.emp_status, '') ILIKE '%active%'
  AND e.designation_department IS NOT NULL
  AND TRIM(e.designation_department) <> ''
GROUP BY e.designation_department
ORDER BY headcount DESC, department
LIMIT {limit};"""


def build_headcount_by_branch_sql(
    question: str,
    *,
    max_rows: Optional[int] = None,
) -> str:
    mart = mart_schema_for_hints()
    limit = max_rows if max_rows is not None else _parse_limit(question)
    return f"""SELECT
    e.location_name AS branch,
    COUNT(DISTINCT e.employee_sk) AS headcount
FROM {mart}.mart_employee_current e
WHERE COALESCE(e.emp_status, '') ILIKE '%active%'
  AND e.location_name IS NOT NULL
  AND TRIM(e.location_name) <> ''
GROUP BY e.location_name
ORDER BY headcount DESC, branch
LIMIT {limit};"""


def try_build_headcount_breakdown_sql(question: str) -> Optional[str]:
    if not looks_like_headcount_breakdown(question):
        return None
    if _BY_BRANCH_RE.search(question or "") and not _BY_DEPARTMENT_RE.search(question or ""):
        return build_headcount_by_branch_sql(question)
    return build_headcount_by_department_sql(question)


_ATTENDANCE_SUMMARY_RE = re.compile(
    r"\battendance\b.*\bsummary\b|\battendance\s+summary\b",
    re.IGNORECASE,
)
_THIS_MONTH_RE = re.compile(r"\b(?:this|current)\s+month\b", re.IGNORECASE)


def _yyyymm_int(date_sql: str) -> str:
    """Warehouse ``month`` on attendance views is integer YYYYMM."""
    return (
        f"(EXTRACT(YEAR FROM {date_sql})::int * 100 + "
        f"EXTRACT(MONTH FROM {date_sql})::int)"
    )


def _attendance_view_schema() -> str:
    return _semantic_view_schema()


def looks_like_attendance_summary(question: str) -> bool:
    q = (question or "").strip()
    if not q:
        return False
    if _ATTENDANCE_SUMMARY_RE.search(q):
        return True
    return bool(
        re.search(r"\battendance\b", q, re.I) and re.search(r"\bsummary\b", q, re.I)
    )


def build_attendance_summary_sql(question: str) -> str:
    """Monthly attendance KPIs from vw_attendance_summary (warehouse: month, late_count)."""
    schema = _attendance_view_schema()
    if _THIS_MONTH_RE.search(question):
        period_filter = f"a.month = {_yyyymm_int('CURRENT_DATE')}"
        limit = 1
    else:
        window_start = "DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '11 months'"
        period_filter = f"a.month >= {_yyyymm_int(window_start)}"
        limit = 12
    return f"""SELECT
    a.month AS period_label,
    COUNT(DISTINCT a.employee_sk) AS employees,
    SUM(COALESCE(a.late_count, 0)) AS late_events,
    SUM(COALESCE(a.overtime_hours, 0)) AS overtime_hours
FROM {schema}.vw_attendance_summary a
WHERE {period_filter}
GROUP BY a.month
ORDER BY a.month DESC
LIMIT {limit};"""


def try_build_attendance_summary_sql(question: str) -> Optional[str]:
    if not looks_like_attendance_summary(question):
        return None
    return build_attendance_summary_sql(question)
