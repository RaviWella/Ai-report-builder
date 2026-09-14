"""MintHRM — HR metrics Pydantic schemas.

Extracted from hr_metrics.py and hr_employment.py / hr_payroll.py to follow
the mint-analytics pattern of keeping all Pydantic models in app/schemas/.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


# ── Generic metric ───────────────────────────────────────────────────

class MetricResponse(BaseModel):
    name: str
    display_name: str
    unit: str
    value: Optional[float]
    period_label: Optional[str] = None
    department_id: Optional[int] = None
    branch_id: Optional[int] = None
    derivation: str = ""
    components: Dict[str, float] = {}


# ── Headcount / employment ───────────────────────────────────────────

class HeadcountSummary(BaseModel):
    tenant_id: str
    period_label: Optional[str]
    total_headcount: Optional[float]
    new_hires: Optional[float]
    separations: Optional[float]
    turnover_rate: Optional[float]


class EmploymentSummary(BaseModel):
    tenant_id: str
    period_label: Optional[str] = None
    active_headcount: int = 0
    employees_with_salary: int = 0
    average_basic_salary: Optional[float] = None
    total_basic_salary_cost: Optional[float] = None
    new_hires: int = 0
    separations: int = 0
    turnover_rate: Optional[float] = None
    latest_month_active_headcount: Optional[int] = None
    mom_active_change: Optional[float] = None
    monthly_salary_cost_active: Optional[float] = None
    salary_band_count: int = 0


class EmployeeListResponse(BaseModel):
    tenant_id: str
    total: int
    limit: int
    offset: int
    items: List[Dict[str, Any]]


# ── Payroll ──────────────────────────────────────────────────────────

class PayrollSummary(BaseModel):
    tenant_id: str
    period_label: Optional[str]
    payroll_employee_count: Optional[int] = None
    total_payroll_cost: Optional[float] = None
    average_salary: Optional[float] = None
    total_gross: Optional[float] = None
    total_additions: Optional[float] = None
    total_tax: Optional[float] = None
    total_statutory: Optional[float] = None
    total_overtime_cost: Optional[float] = None  # legacy alias → total_additions


class PayrollMartSummary(BaseModel):
    tenant_id: str
    period_label: Optional[str] = None
    payroll_employee_count: int = 0
    total_payroll_cost: Optional[float] = None
    average_salary: Optional[float] = None
    total_gross: Optional[float] = None
    total_additions: Optional[float] = None
    total_deductions: Optional[float] = None
    total_tax: Optional[float] = None
    total_epf_employee: Optional[float] = None
    total_epf_employer: Optional[float] = None
    total_etf: Optional[float] = None
    total_statutory: Optional[float] = None
    total_pay_cut: Optional[float] = None
    total_increment: Optional[float] = None


class PayrollRegisterResponse(BaseModel):
    tenant_id: str
    period_label: Optional[str]
    total: int
    limit: int
    offset: int
    items: List[Dict[str, Any]]


# ── Attendance / leave / performance ────────────────────────────────

class AttendanceSummary(BaseModel):
    tenant_id: str
    period_label: Optional[str]
    attendance_rate: Optional[float]
    late_arrivals: Optional[float]
    total_overtime_hours: Optional[float]


class LeaveSummary(BaseModel):
    tenant_id: str
    period_label: Optional[str]
    leave_days_taken: Optional[float]
    leave_days_entitled: Optional[float]
    leave_utilization_rate: Optional[float]
    sick_leave_days: Optional[float]


class PerformanceSummary(BaseModel):
    tenant_id: str
    period_label: Optional[str]
    average_performance_score: Optional[float]
    high_performers: Optional[float]


# ── ETL ──────────────────────────────────────────────────────────────

class EtlRunRequest(BaseModel):
    run_type: str = "incremental"  # "full_load" | "incremental"
    triggered_by: str = "api"
