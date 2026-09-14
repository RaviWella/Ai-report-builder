"""
Per-domain required and allowed warehouse tables.

Required tables must appear in schema link output before SQL generation (fail closed).
Allowed tables cap what survives domain-scoped pruning (reduces payroll noise on recruitment).
"""
from __future__ import annotations

from .domain import DatamartDomain

# Minimum tables the linker must ground per domain (short names).
DOMAIN_REQUIRED_TABLES: dict[DatamartDomain, tuple[str, ...]] = {
    DatamartDomain.RECRUITMENT: (
        "fact_recruitment_pipeline",
        "dim_candidate",
        "dim_org_unit",
    ),
    DatamartDomain.LEAVE: (
        "fact_leave_balance",
        "mart_employee_current",
    ),
    DatamartDomain.PAYROLL: (
        "vw_payroll_summary",
        "mart_employee_current",
    ),
    DatamartDomain.ATTENDANCE: (
        "vw_attendance_summary",
        "mart_employee_current",
    ),
    DatamartDomain.WORKFORCE: (
        "mart_employee_current",
    ),
    DatamartDomain.ATTRITION: (
        "vw_turnover",
        "vw_headcount",
        "mart_employee_current",
    ),
    DatamartDomain.HEADCOUNT: (
        "mart_headcount_monthly",
        "vw_headcount",
        "mart_employee_current",
    ),
}

# Tables that may appear in the grounded packet for this domain (pruning allowlist).
DOMAIN_ALLOWED_TABLES: dict[DatamartDomain, frozenset[str]] = {
    DatamartDomain.RECRUITMENT: frozenset(
        {
            "fact_recruitment_pipeline",
            "dim_candidate",
            "dim_job",
            "dim_requisition",
            "dim_org_unit",
            "dim_employee",
            "mart_employee_current",
        }
    ),
    DatamartDomain.LEAVE: frozenset(
        {
            "fact_leave_balance",
            "fact_leave_transaction",
            "vw_leave_summary",
            "dim_leave_type",
            "dim_employee",
            "mart_employee_current",
        }
    ),
    DatamartDomain.PAYROLL: frozenset(
        {
            "vw_payroll_summary",
            "dim_payroll_group",
            "dim_payroll_period",
            "fact_payroll",
            "fact_payroll_detail",
            "fct_processed_salary",
            "fct_processed_tax",
            "fct_compliance_payroll",
            "mart_processed_payroll_summary",
            "mart_employee_current",
            "dim_employee",
            "snap_employee",
            "vw_salary_bands",
            "fct_processed_add_ded",
            "dim_canonical_pay_item",
            "fct_processed_loan_deduction",
            "mart_salary_band_summary",
            "fct_salary_change",
            "fact_leave_balance",
            "vw_leave_summary",
        }
    ),
    DatamartDomain.ATTENDANCE: frozenset(
        {
            "vw_attendance_summary",
            "mart_attendance_monthly_summary",
            "fact_attendance",
            "fct_overtime",
            "mart_employee_current",
            "dim_employee",
            "mart_headcount_monthly",
            "dim_designation",
        }
    ),
    DatamartDomain.WORKFORCE: frozenset(
        {
            "mart_employee_current",
            "dim_employee",
            "dim_org_unit",
            "dim_designation",
            "dim_company",
            "dim_branch",
            "snap_employee",
            "vw_headcount",
            "vw_performance_summary",
        }
    ),
    DatamartDomain.ATTRITION: frozenset(
        {
            "vw_turnover",
            "vw_headcount",
            "fct_lifecycle_event",
            "vw_lifecycle_summary",
            "vw_employment_monthly",
            "mart_employee_current",
            "dim_employee",
        }
    ),
    DatamartDomain.HEADCOUNT: frozenset(
        {
            "mart_headcount_monthly",
            "vw_headcount",
            "mart_employee_current",
            "dim_employee",
            "dim_designation",
            "fct_lifecycle_event",
            "vw_lifecycle_summary",
            "hr_snap",
            "snap_employee",
        }
    ),
}


def required_tables_for_domain(domain: DatamartDomain) -> tuple[str, ...]:
    return DOMAIN_REQUIRED_TABLES.get(domain, ())


def allowed_tables_for_domain(domain: DatamartDomain) -> frozenset[str] | None:
    if domain in (DatamartDomain.MIXED, DatamartDomain.UNKNOWN):
        return None
    return DOMAIN_ALLOWED_TABLES.get(domain)
