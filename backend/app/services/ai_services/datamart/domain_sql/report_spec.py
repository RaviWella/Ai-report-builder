"""
Compile a fast, deterministic ReportSpec from the user question.

Drives retrieval must-include tables, catalog SQL routing, and pre-execute gates
without an extra LLM call.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from ..orchestration.intent_router import ChatIntent
from .metric_templates import question_wants_row_detail


class ReportDomain(str, Enum):
    LEAVE = "leave"
    ATTENDANCE = "attendance"
    PAYROLL = "payroll"
    WORKFORCE = "workforce"
    ATTRITION = "attrition"
    HEADCOUNT = "headcount"
    GENERIC = "generic"


class ReportType(str, Enum):
    DETAIL_LIST = "detail_list"
    SCALAR = "scalar"
    SUMMARY = "summary"
    RANKING = "ranking"


@dataclass
class ReportSpec:
    domain: ReportDomain
    report_type: ReportType
    required_output_columns: list[str] = field(default_factory=list)
    """Logical field ids (employee_name, leave_type, …) for compliance checks."""
    required_tables: list[str] = field(default_factory=list)
    sql_filters: list[str] = field(default_factory=list)
    """Human-readable filter hints (e.g. approved leave) for prompts and checks."""
    template_id: Optional[str] = None
    forbidden_table_only: list[str] = field(default_factory=list)
    """If SQL uses only this table without required_tables, block execution."""


_FIELD_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("employee_name", re.compile(r"\bemployee\s+name\b", re.I)),
    ("employee_id", re.compile(r"\bemployee\s+(?:id|no|number)\b", re.I)),
    ("company", re.compile(r"\bcompany\b", re.I)),
    ("branch", re.compile(r"\bbranch\b", re.I)),
    ("department", re.compile(r"\bdepartment\b", re.I)),
    ("organization_unit", re.compile(r"\borganization\s+unit\b", re.I)),
    ("designation", re.compile(r"\bdesignation\b", re.I)),
    ("job_title", re.compile(r"\bjob\s+title\b", re.I)),
    ("reporting_manager", re.compile(r"\breporting\s+manager\b", re.I)),
    ("salary", re.compile(r"\b(?:salary|basic\s+salary|gross\s+pay|net\s+pay)\b", re.I)),
    ("payroll_group_name", re.compile(r"\bpayroll\s+group\b", re.I)),
    ("pay_frequency", re.compile(r"\bpay\s+frequency\b", re.I)),
    ("currency_code", re.compile(r"\bcurrency(?:\s+code)?\b", re.I)),
    ("leave_type", re.compile(r"\bleave\s+type\b", re.I)),
    ("leave_start_date", re.compile(r"\bleave\s+start\s+date\b", re.I)),
    ("leave_end_date", re.compile(r"\bleave\s+end\s+date\b", re.I)),
    ("leave_days", re.compile(r"\b(?:total\s+)?leave\s+days\b", re.I)),
    ("leave_status", re.compile(r"\bleave\s+status\b", re.I)),
    ("period_label", re.compile(r"\b(?:this|current)\s+month\b|\bperiod\b", re.I)),
]

_DOMAIN_TABLES: dict[ReportDomain, list[str]] = {
    ReportDomain.LEAVE: [
        "fact_leave_transaction",
        "dim_leave_type",
        "fact_leave_balance",
        "dim_employee",
        "vw_leave_summary",
    ],
    ReportDomain.ATTENDANCE: [
        "vw_attendance_summary",
        "mart_employee_current",
    ],
    ReportDomain.PAYROLL: [
        "fact_payroll_detail",
        "fact_payroll",
        "dim_employee",
    ],
    ReportDomain.WORKFORCE: ["mart_employee_current"],
    ReportDomain.ATTRITION: [
        "vw_turnover",
        "vw_headcount",
        "mart_employee_current",
    ],
    ReportDomain.HEADCOUNT: ["vw_headcount", "dim_employee", "mart_employee_current"],
    ReportDomain.GENERIC: ["dim_employee"],
}

# Map logical field id → SQL column name fragments for pre-execute checks.
_FIELD_SQL_FRAGMENTS: dict[str, tuple[str, ...]] = {
    "employee_name": ("employee_name", "emp_fullname", "full_name", "emp_name"),
    "employee_id": ("employee_id", "employee_no", "emp_no", "emp_id"),
    "company": ("company", "legal_entity", "company_name"),
    "branch": ("branch", "branch_name", "location_name"),
    "department": ("department", "designation_department", "department_name"),
    "organization_unit": ("organization_unit", "emp_position", "org_unit"),
    "designation": ("designation", "job_title", "designation_id"),
    "job_title": ("job_title", "designation", "title"),
    "reporting_manager": (
        "reporting_manager",
        "superior_emp_no",
        "superior_fullname",
        "manager",
    ),
    "salary": ("basic_salary", "gross_pay", "net_pay", "salary"),
    "payroll_group_name": ("payroll_group_name", "payroll_group"),
    "pay_frequency": ("payroll_frequency", "pay_frequency"),
    "currency_code": ("currency_code",),
    "leave_type": ("leave_type_name", "leave_type"),
    "leave_start_date": ("leave_start_date", "leave_start", "period_label"),
    "leave_end_date": ("leave_end_date", "leave_end", "period_label"),
    "leave_days": ("leave_days", "total_leave_days", "days_approved", "days_taken"),
    "leave_status": ("leave_status_name", "leave_status"),
    "period_label": ("period_label", "year_month"),
}


_RECRUITMENT_DOMAIN = re.compile(
    r"\b(?:recruitment|recruit|hiring|candidate|candidates|applicant|"
    r"recruitment\s+pipeline|pipeline\s+report|linkedin|referral|referrals|"
    r"requisition|time\s+to\s+hire|expected\s+joining)\b",
    re.I,
)


def _detect_domain(q: str) -> ReportDomain:
    # Recruitment lists must not be classified as workforce via "employee referrals".
    if _RECRUITMENT_DOMAIN.search(q):
        return ReportDomain.GENERIC
    if re.search(r"\b(?:attrition|turnover)\s+rate\b", q, re.I) or (
        re.search(r"\b(?:attrition|turnover)\b", q, re.I)
        and re.search(r"\b(?:highest|rate|rank|department|branch)\b", q, re.I)
    ):
        return ReportDomain.ATTRITION
    if re.search(
        r"\bleave\b|\btime\s+off\b|\bvacation\b|\bsick\s+leave\b|\bleave\s+transaction\b",
        q,
        re.I,
    ):
        return ReportDomain.LEAVE
    if re.search(r"\battendance\b", q, re.I):
        return ReportDomain.ATTENDANCE
    if re.search(
        r"\bpayroll\b|\bpayslip\b|\bgross\s+pay\b|\bnet\s+pay\b|\bpay\s+period\b",
        q,
        re.I,
    ):
        return ReportDomain.PAYROLL
    if question_wants_row_detail(q) and re.search(
        r"\b(?:employee|employees|staff)\b", q, re.I
    ) and not re.search(r"\bleave\b|\battendance\b|\bpayroll\b|\bpayslip\b", q, re.I):
        return ReportDomain.WORKFORCE
    if re.search(r"\bworkforce\s+report\b|\bemployee\s+master\b|\borg\s+chart\b", q, re.I):
        return ReportDomain.WORKFORCE
    if re.search(r"\bheadcount\b|\bhead\s+count\b|\bemployee\s+count\b", q, re.I):
        return ReportDomain.HEADCOUNT
    if re.search(
        r"\bcombining\s+employee\b|\bemployee\s+listing\b|\borganization\s+data\b",
        q,
        re.I,
    ) and not re.search(r"\bleave\b|\battendance\b|\bpayroll\b", q, re.I):
        return ReportDomain.WORKFORCE
    return ReportDomain.GENERIC


def _detect_report_type(q: str, domain: ReportDomain) -> ReportType:
    if domain == ReportDomain.ATTENDANCE and re.search(
        r"\battendance\s+summary\b", q, re.I
    ):
        return ReportType.SUMMARY
    if re.search(r"\battendance\b.*\bsummary\b", q, re.I):
        return ReportType.SUMMARY
    if re.search(
        r"\b(?:top|first|highest)\s+\d+\b.*\b(?:paid|salary)\b",
        q,
        re.I,
    ) or (
        re.search(r"\btop\b", q, re.I)
        and re.search(r"\b(?:paid|salary)\b", q, re.I)
        and re.search(r"\b\d+\b", q)
    ):
        return ReportType.RANKING
    if re.search(
        r"\b(?:how\s+many|count|number\s+of|total\s+number|what\s+is\s+the)\b",
        q,
        re.I,
    ) and not question_wants_row_detail(q):
        return ReportType.SCALAR
    if question_wants_row_detail(q):
        return ReportType.DETAIL_LIST
    if domain == ReportDomain.ATTRITION:
        return ReportType.RANKING
    return ReportType.DETAIL_LIST


def _is_employee_bank_detail_list(q: str) -> bool:
    return bool(
        question_wants_row_detail(q)
        and re.search(r"\bbank\b", q, re.I)
        and re.search(r"\b(?:employee|employees|staff)\b", q, re.I)
    )


def _pick_template(domain: ReportDomain, report_type: ReportType, q: str) -> Optional[str]:
    if (
        domain == ReportDomain.WORKFORCE
        and report_type == ReportType.DETAIL_LIST
        and _is_employee_bank_detail_list(q)
    ):
        return "workforce.employee_bank_detail"
    if domain == ReportDomain.LEAVE and report_type == ReportType.DETAIL_LIST:
        return "leave.detail_list"
    if domain == ReportDomain.ATTENDANCE and report_type == ReportType.SUMMARY:
        return "attendance.monthly_summary"
    if domain == ReportDomain.ATTRITION and report_type in (
        ReportType.RANKING,
        ReportType.DETAIL_LIST,
    ):
        return "attrition.rate_by_department"
    if domain == ReportDomain.PAYROLL and report_type == ReportType.DETAIL_LIST:
        return "payroll.summary_detail"
    if domain == ReportDomain.WORKFORCE and report_type == ReportType.DETAIL_LIST:
        return "workforce.roster"
    if report_type == ReportType.RANKING and re.search(r"\b(?:paid|salary)\b", q, re.I):
        return "top_paid.ranking"
    return None


def _extract_columns(q: str) -> list[str]:
    found: list[str] = []
    for field_id, pattern in _FIELD_PATTERNS:
        if pattern.search(q):
            found.append(field_id)
    return found


def _extract_filters(q: str, domain: ReportDomain) -> list[str]:
    filters: list[str] = []
    if re.search(r"\bapproved\b|\bapproval\b", q, re.I):
        # "attendance approval group" is not leave approval.
        if domain != ReportDomain.ATTENDANCE or re.search(r"\bleave\b", q, re.I):
            filters.append("approved_leave")
    if domain == ReportDomain.ATTENDANCE and re.search(
        r"\b(?:this|current)\s+month\b", q, re.I
    ):
        filters.append("current_month")
    return filters


def compile_report_spec(
    question: str,
    *,
    chat_intent: Optional[ChatIntent] = None,
) -> ReportSpec:
    """Fast deterministic intent compile (no LLM)."""
    q = (question or "").strip()
    if chat_intent in (ChatIntent.REFINE_SQL, ChatIntent.POST_PROCESS_ONLY):
        return ReportSpec(
            domain=ReportDomain.GENERIC,
            report_type=ReportType.DETAIL_LIST,
        )

    domain = _detect_domain(q)
    report_type = _detect_report_type(q, domain)
    columns = _extract_columns(q)
    tables = list(_DOMAIN_TABLES.get(domain, _DOMAIN_TABLES[ReportDomain.GENERIC]))
    filters = _extract_filters(q, domain)
    template_id = _pick_template(domain, report_type, q)

    forbidden: list[str] = []
    if domain == ReportDomain.LEAVE:
        forbidden.append("mart_employee_current")
    if domain == ReportDomain.ATTENDANCE:
        forbidden.append("mart_employee_current")

    return ReportSpec(
        domain=domain,
        report_type=report_type,
        required_output_columns=columns,
        required_tables=tables,
        sql_filters=filters,
        template_id=template_id,
        forbidden_table_only=forbidden,
    )


def spec_required_tables(spec: ReportSpec) -> set[str]:
    return {t.lower() for t in spec.required_tables}


def field_sql_fragments(field_id: str) -> tuple[str, ...]:
    return _FIELD_SQL_FRAGMENTS.get(field_id, (field_id.replace("_", " "),))
