"""
Route ReportSpec.template_id to deterministic catalog SQL (fast path, no LLM).
"""
from __future__ import annotations

import logging
from typing import Optional

from .catalog_report_sql import (
    try_build_attendance_summary_sql,
    try_build_attrition_rate_report_sql,
)
from .employee_bank_detail_sql import try_build_employee_bank_detail_sql
from .leave_report_sql import try_build_leave_detail_report_sql
from .payroll_report_sql import try_build_payroll_detail_report_sql
from ..schema_broker import SchemaGrounding
from .report_spec import ReportSpec, ReportDomain, ReportType
from .workforce_sql_template import try_build_top_paid_report_sql, try_build_workforce_report_sql

logger = logging.getLogger("ai_services.datamart.report_sql")


def _payroll_template_tag(sql: Optional[str]) -> str:
    sql_l = (sql or "").lower()
    if "vw_payroll_summary" in sql_l:
        return "payroll_summary_view_template"
    if "mart_processed_payroll_summary" in sql_l:
        return "payroll_processed_summary_template"
    if "fact_payroll" in sql_l or "fct_processed_salary" in sql_l:
        return "payroll_fact_template"
    return "payroll_mart_group_template"


def _leave_template_tag(sql: Optional[str]) -> str:
    sql_l = (sql or "").lower()
    if "fact_leave_transaction" in sql_l:
        return "leave_detail_template"
    if "fact_leave_balance" in sql_l:
        return "leave_balance_template"
    if "vw_leave_summary" in sql_l:
        return "leave_summary_view_template"
    return "leave_detail_template"


def try_build_sql_from_report_spec(
    question: str,
    spec: ReportSpec,
    *,
    grounded_short_names: Optional[list[str]] = None,
    grounding: Optional[SchemaGrounding] = None,
) -> Optional[tuple[str, str]]:
    """
    Return (sql, source_tag) when a governed template matches the spec.
    """
    tid = spec.template_id
    if tid == "payroll.summary_detail" and spec.domain == ReportDomain.PAYROLL:
        sql = try_build_payroll_detail_report_sql(
            question,
            grounded_short_names=grounded_short_names,
            grounding=grounding,
        )
        if sql:
            tag = _payroll_template_tag(sql)
            return sql, tag
    if tid == "leave.detail_list" and spec.domain == ReportDomain.LEAVE:
        sql = try_build_leave_detail_report_sql(
            question,
            grounded_short_names=grounded_short_names,
            grounding=grounding,
        )
        if sql:
            tag = _leave_template_tag(sql)
            return sql, tag
    if tid == "attendance.monthly_summary" and spec.domain == ReportDomain.ATTENDANCE:
        sql = try_build_attendance_summary_sql(question)
        if sql:
            return sql, "attendance_summary_template"
    if tid == "attrition.rate_by_department" and spec.domain == ReportDomain.ATTRITION:
        sql = try_build_attrition_rate_report_sql(question)
        if sql:
            return sql, "attrition_rate_template"
    if tid == "workforce.employee_bank_detail" and spec.domain == ReportDomain.WORKFORCE:
        if grounding is not None:
            sql = try_build_employee_bank_detail_sql(question, grounding=grounding)
            if sql:
                return sql, "employee_bank_detail_template"
    if tid == "workforce.roster" and spec.domain == ReportDomain.WORKFORCE:
        sql = try_build_workforce_report_sql(question)
        if sql:
            return sql, "workforce_template"
    if tid == "top_paid.ranking" and spec.report_type == ReportType.RANKING:
        sql = try_build_top_paid_report_sql(question)
        if sql:
            return sql, "top_paid_template"

    if spec.domain == ReportDomain.LEAVE and spec.report_type == ReportType.DETAIL_LIST:
        sql = try_build_leave_detail_report_sql(
            question,
            grounded_short_names=grounded_short_names,
            grounding=grounding,
        )
        if sql:
            tag = _leave_template_tag(sql)
            return sql, tag
    if spec.domain == ReportDomain.ATTENDANCE and spec.report_type == ReportType.SUMMARY:
        sql = try_build_attendance_summary_sql(question)
        if sql:
            return sql, "attendance_summary_template"
    if spec.domain == ReportDomain.PAYROLL and spec.report_type == ReportType.DETAIL_LIST:
        sql = try_build_payroll_detail_report_sql(
            question,
            grounded_short_names=grounded_short_names,
            grounding=grounding,
        )
        if sql:
            return sql, _payroll_template_tag(sql)

    return None
