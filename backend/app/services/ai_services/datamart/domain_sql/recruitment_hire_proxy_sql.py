"""
Recruitment analytics proxy when ``fact_recruitment_pipeline`` is not in the warehouse.

Uses hire/join lifecycle events + current employee mart (and optional dim_employee email).
Documented fallback for demo tenants until recruitment facts are modeled in dbt.
"""
from __future__ import annotations

import re
from typing import Optional

from ..config import MAX_RESULT_ROWS
from ..schema_broker import SchemaGrounding

_HIRE_PROXY_RE = re.compile(
    r"\b(?:recruitment|recruit|hiring|candidate|candidates|applicant|"
    r"pipeline|requisition|time-to-hire|time\s+to\s+hire|linkedin|referral)\b",
    re.IGNORECASE,
)

_HIRE_CTE = """hire_pipeline AS (
  SELECT
    e.emp_fullname AS candidate_name,
    d.email AS contact_email,
    CASE
      WHEN COALESCE(e.employee_category, '') ILIKE '%referral%' THEN 'Employee Referral'
      WHEN COALESCE(e.employee_category, '') ILIKE '%linkedin%' THEN 'LinkedIn'
      ELSE COALESCE(
        NULLIF(TRIM(e.employee_category), ''),
        NULLIF(TRIM(e.employment_type), ''),
        'Other'
      )
    END AS recruitment_source,
    le.approved_date AS appointment_date,
    COALESCE(e.join_date, le.effective_date) AS expected_joining_date,
    e.location_name AS assigned_branch,
    le.event_name AS current_stage,
    e.designation_department,
    e.designation
  FROM hr.fct_lifecycle_event le
  JOIN hr.mart_employee_current e ON e.employee_sk = le.employee_sk
  LEFT JOIN hr.dim_employee d
    ON d.employee_sk = e.employee_sk AND d.is_current IS TRUE
  WHERE le.event_name ILIKE '%join%'
     OR le.event_category ILIKE '%hire%'
)"""


def warehouse_has_recruitment_pipeline(grounding: SchemaGrounding) -> bool:
    shorts = {s.lower() for s in grounding.table_short_names}
    return "fact_recruitment_pipeline" in shorts


def looks_like_recruitment_hire_proxy(question: str) -> bool:
    return bool(_HIRE_PROXY_RE.search((question or "").strip()))


def _source_filter(question: str) -> str:
    q = question.lower()
    parts: list[str] = []
    if "linkedin" in q:
        parts.append("hp.recruitment_source ILIKE '%linkedin%'")
    if "referral" in q:
        parts.append("hp.recruitment_source ILIKE '%referral%'")
    if not parts:
        return ""
    return " AND (" + " OR ".join(parts) + ")"


def _join_window_filter(question: str) -> str:
    m = re.search(r"\b(?:next|within)\s+(\d+)\s+days?\b", question, re.I)
    days = int(m.group(1)) if m else None
    if days is not None:
        return (
            f" AND hp.expected_joining_date >= CURRENT_DATE - INTERVAL '{days} days'"
            f" AND hp.expected_joining_date < CURRENT_DATE + INTERVAL '{days} days'"
        )
    if re.search(r"\bnext\s+90\s+days\b", question, re.I):
        return (
            " AND hp.expected_joining_date >= CURRENT_DATE - INTERVAL '90 days'"
            " AND hp.expected_joining_date < CURRENT_DATE + INTERVAL '90 days'"
        )
    if re.search(r"\bnext\s+60\s+days\b", question, re.I):
        return (
            " AND hp.expected_joining_date >= CURRENT_DATE - INTERVAL '60 days'"
            " AND hp.expected_joining_date < CURRENT_DATE + INTERVAL '60 days'"
        )
    if re.search(r"\bnext\s+30\s+days\b", question, re.I):
        return (
            " AND hp.expected_joining_date >= CURRENT_DATE - INTERVAL '30 days'"
            " AND hp.expected_joining_date < CURRENT_DATE + INTERVAL '30 days'"
        )
    if re.search(r"\blast\s+quarter\b", question, re.I):
        return (
            " AND hp.appointment_date >= date_trunc('quarter', CURRENT_DATE)"
            " - INTERVAL '3 months'"
            " AND hp.appointment_date < date_trunc('quarter', CURRENT_DATE)"
        )
    if re.search(r"\blast\s+six\s+months\b", question, re.I):
        return (
            " AND hp.expected_joining_date >= CURRENT_DATE - INTERVAL '6 months'"
        )
    return " AND hp.expected_joining_date >= CURRENT_DATE - INTERVAL '1 year'"


def try_build_recruitment_hire_proxy_sql(
    question: str,
    *,
    grounding: Optional[SchemaGrounding] = None,
    max_rows: Optional[int] = None,
) -> Optional[str]:
    """
    Build executable recruitment-shaped SQL from hire lifecycle when pipeline facts are absent.
    """
    q = (question or "").strip()
    if not q or not looks_like_recruitment_hire_proxy(q):
        return None
    if grounding is not None and warehouse_has_recruitment_pipeline(grounding):
        return None

    limit = max_rows if max_rows is not None else MAX_RESULT_ROWS
    src = _source_filter(q)
    window = _join_window_filter(q)

    if re.search(r"\btime[- ]to[- ]hire\b", q, re.I):
        return f"""WITH {_HIRE_CTE}
SELECT
  hp.recruitment_source,
  ROUND(
    AVG(
      (hp.expected_joining_date::date - COALESCE(hp.appointment_date, hp.expected_joining_date)::date)
    )::numeric,
    1
  ) AS avg_time_to_hire_days
FROM hire_pipeline hp
WHERE hp.expected_joining_date IS NOT NULL
  {window}
GROUP BY hp.recruitment_source
ORDER BY avg_time_to_hire_days DESC
LIMIT {limit};"""

    if re.search(r"\brecruitment\s+sources?\b", q, re.I) and re.search(
        r"\b(?:most|appointed|last\s+quarter)\b", q, re.I
    ):
        return f"""WITH {_HIRE_CTE}
SELECT
  hp.recruitment_source,
  COUNT(*) AS candidate_count
FROM hire_pipeline hp
WHERE 1=1
  {window}
GROUP BY hp.recruitment_source
ORDER BY candidate_count DESC
LIMIT {limit};"""

    if re.search(r"\bopen\s+requisitions?\b", q, re.I):
        return f"""WITH {_HIRE_CTE}
SELECT
  hp.designation AS requisition_title,
  hp.designation_department AS department,
  COUNT(*) AS active_candidates,
  STRING_AGG(DISTINCT hp.recruitment_source, ', ' ORDER BY hp.recruitment_source) AS recruitment_source_mix,
  hp.assigned_branch AS branch
FROM hire_pipeline hp
WHERE 1=1
  {window}
GROUP BY hp.designation, hp.designation_department, hp.assigned_branch
ORDER BY active_candidates DESC
LIMIT {limit};"""

    if re.search(r"\bgrouped\s+by\s+branch\b", q, re.I):
        return f"""WITH {_HIRE_CTE}
SELECT
  hp.assigned_branch AS branch,
  hp.recruitment_source,
  hp.current_stage,
  hp.expected_joining_date,
  COUNT(*) AS candidate_count
FROM hire_pipeline hp
WHERE 1=1
  {window}
GROUP BY hp.assigned_branch, hp.recruitment_source, hp.current_stage, hp.expected_joining_date
ORDER BY 1, 4
LIMIT {limit};"""

    # Default: candidate-level pipeline list
    return f"""WITH {_HIRE_CTE}
SELECT
  hp.candidate_name,
  hp.contact_email,
  hp.recruitment_source,
  hp.appointment_date,
  hp.expected_joining_date,
  hp.assigned_branch
FROM hire_pipeline hp
WHERE 1=1
  {src}
  {window}
ORDER BY hp.expected_joining_date
LIMIT {limit};"""
