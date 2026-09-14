"""
Resolve SQL from governed templates before calling the LLM.

Keeps chat/modify/add-scenario flows intact while making common list reports
fast and accurate (employee+bank, workforce, payroll, leave, attendance).
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from ..domain_sql.employee_bank_detail_sql import try_build_employee_bank_detail_sql
from ..domain_sql.employee_list_sql import try_build_employee_list_sql
from ..domain_sql.employee_shift_sql import try_build_employee_shift_list_sql
from ..domain_sql.recruitment_pipeline_sql import try_build_recruitment_pipeline_sql
from ..domain_sql.leave_report_sql import try_build_leave_detail_report_sql
from ..domain_sql.payroll_report_sql import try_build_payroll_detail_report_sql
from ..domain_sql.report_spec import ReportSpec, compile_report_spec
from ..domain_sql.report_sql_router import try_build_sql_from_report_spec
from ..schema_broker import SchemaGrounding
from ..domain_sql.catalog_report_sql import try_build_headcount_breakdown_sql
from .sql_generation import (
    try_attendance_summary_template_sql,
    try_attrition_rate_template_sql,
    try_top_paid_template_sql,
    try_workforce_template_sql,
)
from ..domain_sql.workforce_sql_template import try_build_workforce_report_sql

logger = logging.getLogger("ai_services.datamart.sql_fast_path")


def try_resolve_deterministic_sql(
    question: str,
    *,
    grounding: SchemaGrounding,
    report_spec: Optional[ReportSpec] = None,
    chat_intent_value: str = "new_query",
) -> Optional[tuple[str, str, str]]:
    """
    Return (sql, source_tag, narrative) when a template matches.

    Order matters: specific reports before generic workforce roster.
    """
    if not grounding.columns_by_table:
        return None

    recruitment_sql = try_build_recruitment_pipeline_sql(
        question, grounding=grounding
    )
    if recruitment_sql:
        return (
            recruitment_sql,
            "recruitment_pipeline_template",
            "Recruitment pipeline candidates with source, dates, and branch.",
        )

    # Employee list + bank — before report-spec / LLM.
    bank_sql = try_build_employee_bank_detail_sql(question, grounding=grounding)
    if bank_sql:
        return (
            bank_sql,
            "employee_bank_detail_template",
            "Employee number, name, employment category, and bank details from the "
            "workforce mart and salary bank tables.",
        )

    shift_sql = try_build_employee_shift_list_sql(question, grounding=grounding)
    if shift_sql:
        return (
            shift_sql,
            "employee_shift_template",
            "Employee number, name, and shift from the workforce mart joined to dim_shift.",
        )

    spec = report_spec
    if spec is None:
        spec = compile_report_spec(question)

    if spec:
        routed = try_build_sql_from_report_spec(
            question,
            spec,
            grounded_short_names=grounding.table_short_names,
            grounding=grounding,
        )
        if routed:
            sql, tag = routed
            return sql, tag, _narrative_for_tag(tag)

    attendance = try_attendance_summary_template_sql(question)
    if attendance:
        return (
            attendance,
            "attendance_summary_template",
            "Monthly attendance summary (present days, late, overtime).",
        )

    leave_sql = try_build_leave_detail_report_sql(question, grounding=grounding)
    if leave_sql:
        return (
            leave_sql,
            "leave_detail_template",
            "Leave balances and utilization joined to employees.",
        )

    payroll_sql = try_build_payroll_detail_report_sql(question, grounding=grounding)
    if payroll_sql:
        tag = (
            "payroll_summary_view_template"
            if "vw_payroll_summary" in payroll_sql.lower()
            else "payroll_processed_summary_template"
        )
        return payroll_sql, tag, _narrative_for_tag(tag)

    headcount_breakdown = try_build_headcount_breakdown_sql(question)
    if headcount_breakdown:
        return (
            headcount_breakdown,
            "headcount_breakdown_template",
            "Active headcount grouped by department or branch.",
        )

    attrition = try_attrition_rate_template_sql(question)
    if attrition:
        return (
            attrition,
            "attrition_rate_template",
            "Attrition rate by department from turnover and headcount views.",
        )

    top_paid = try_top_paid_template_sql(question)
    if top_paid:
        return (
            top_paid,
            "top_paid_template",
            "Employees ranked by basic salary.",
        )

    workforce = try_build_workforce_report_sql(question)
    if workforce:
        return (
            workforce,
            "workforce_template",
            "Current employees from the workforce mart.",
        )

    list_sql = try_build_employee_list_sql(question, grounding=grounding)
    if list_sql:
        return (
            list_sql,
            "employee_list_template",
            "Employee attributes from the current workforce mart.",
        )

    return None


def _narrative_for_tag(tag: str) -> str:
    return {
        "employee_bank_detail_template": (
            "Employee number, name, employment category, and bank details."
        ),
        "employee_list_template": "Employee detail list from the workforce mart.",
        "employee_shift_template": "Employee list with assigned shift name.",
        "recruitment_pipeline_template": "Recruitment pipeline candidate list.",
        "workforce.roster": "Current employee roster from the workforce mart.",
        "workforce_template": "Current employee roster from the workforce mart.",
        "leave.detail_list": "Leave detail for employees.",
        "leave_detail_template": "Leave detail for employees.",
        "payroll.summary_detail": "Payroll summary per employee and period.",
        "payroll_summary_view_template": "Payslip-style payroll summary.",
        "attendance.monthly_summary": "Monthly attendance KPIs.",
        "attendance_summary_template": "Monthly attendance KPIs.",
        "attrition.rate_by_department": "Attrition rate by department.",
        "attrition_rate_template": "Attrition rate by department.",
        "headcount_breakdown_template": "Active headcount by department or branch.",
        "top_paid.ranking": "Top paid employees.",
        "top_paid_template": "Top paid employees.",
    }.get(tag, "Generated from a governed SQL template.")


# Common LLM hallucination on this warehouse (no vw_employee table).
_HALLUCINATED_TABLE_RE = re.compile(
    r"\b(?:vw_employee|view_employee)\b",
    re.IGNORECASE,
)


def rewrite_hallucinated_table_names(sql: str, grounding: SchemaGrounding) -> str:
    """Replace known-bad table names with mart_employee_current when grounded."""
    if not sql or not _HALLUCINATED_TABLE_RE.search(sql):
        return sql
    shorts = {s.lower() for s in grounding.table_short_names}
    if "mart_employee_current" not in shorts:
        return sql
    return _HALLUCINATED_TABLE_RE.sub("mart_employee_current", sql)
