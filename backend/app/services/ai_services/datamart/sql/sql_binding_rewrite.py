"""
Fast local SQL replacement when binding fails on known hallucinated metric columns.
"""
from __future__ import annotations

import re
from typing import Optional

from ..domain_sql.catalog_report_sql import try_build_attrition_rate_report_sql
from ..domain_sql.employee_bank_detail_sql import try_build_employee_bank_detail_sql
from ..domain_sql.employee_list_sql import try_build_employee_list_sql
from ..domain_sql.employee_shift_sql import try_build_employee_shift_list_sql
from ..domain_sql.leave_report_sql import try_build_leave_detail_report_sql
from ..domain_sql.probation_report_sql import try_build_probation_report_sql
from ..schema_broker import SchemaGrounding

_HALLUCINATED_ATTRITION_COL = re.compile(
    r"\battrition_rate\b|\bturnover_rate\b",
    re.IGNORECASE,
)


def try_binding_catalog_rewrite(
    question: str,
    binding_error: str,
    *,
    sql: str = "",
    grounding: Optional[SchemaGrounding] = None,
) -> Optional[str]:
    """
    Return replacement SQL without an LLM call when the error is a known bad column pattern.
    """
    err = (binding_error or "").lower()
    q = (question or "").lower()
    combined = f"{err} {(sql or '').lower()}"

    if _HALLUCINATED_ATTRITION_COL.search(combined) and (
        "attrition" in q or "turnover" in q or _HALLUCINATED_ATTRITION_COL.search(q)
    ):
        replacement = try_build_attrition_rate_report_sql(question)
        if replacement:
            return replacement

    if "attrition_rate" in err or "turnover_rate" in err:
        if "attrition" in q or "turnover" in q:
            return try_build_attrition_rate_report_sql(question)

    if "leave" in q:
        replacement = try_build_leave_detail_report_sql(question, grounding=grounding)
        if replacement:
            return replacement

    if "probation" in q or "manager_emp_no" in err:
        replacement = try_build_probation_report_sql(question, grounding=grounding)
        if replacement:
            return replacement

    if grounding and re.search(r"\bbank\b", q, re.I):
        replacement = try_build_employee_bank_detail_sql(question, grounding=grounding)
        if replacement:
            return replacement

    if grounding and re.search(r"\bshift\b", q, re.I):
        replacement = try_build_employee_shift_list_sql(question, grounding=grounding)
        if replacement:
            return replacement

    if grounding and (
        "vw_employee" in err
        or "view_employee" in err
        or "dim_employee" in err
        or re.search(r"\b(?:employee|supervisor|manager)\b", q, re.I)
    ):
        replacement = try_build_employee_list_sql(question, grounding=grounding)
        if replacement:
            return replacement

    if grounding and (
        "dim_employee" in err
        or "manager_emp_no" in combined
        or "not in the allowlist" in err
    ):
        replacement = try_build_probation_report_sql(question, grounding=grounding)
        if replacement:
            return replacement

    return None
