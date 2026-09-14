"""Curated business glossary, metrics, governance, and data-quality rules."""

from __future__ import annotations

GLOSSARY: list[dict[str, str]] = [
    {
        "term": "Employee",
        "definition": "A person employed by the organization with a unique employee number (emp_no) in MintHRM.",
        "formula": "TBD",
        "owner": "HR Analytics",
    },
    {
        "term": "Headcount",
        "definition": "Count of employees in active employment status at a point in time or month-end.",
        "formula": "COUNT(employee_sk) WHERE emp_status = 'active' AND is_current = true",
        "owner": "HR Analytics",
    },
    {
        "term": "Active Employee",
        "definition": "Employee whose current employment status is active in dim_employee.",
        "formula": "emp_status = 'active' AND is_current = true",
        "owner": "HR Analytics",
    },
    {
        "term": "Termination",
        "definition": "End of employment due to resignation, termination, or retirement recorded in lifecycle events.",
        "formula": "TBD — see fct_lifecycle_event",
        "owner": "HR Analytics",
    },
    {
        "term": "Leave Balance",
        "definition": "Remaining entitled leave days for an employee and leave type at a snapshot date.",
        "formula": "remaining_days from fct_leave_balance_snapshot / vw_current_leave_balance",
        "owner": "HR Operations",
    },
    {
        "term": "Leave Entitlement",
        "definition": "Total leave days granted to an employee for a leave type and entitlement period.",
        "formula": "entitled_days from fct_leave_balance_snapshot",
        "owner": "HR Operations",
    },
    {
        "term": "Attendance",
        "definition": "Daily record of employee presence, absence, lateness, and worked hours.",
        "formula": "TBD — fct_daily_attendance grain",
        "owner": "Workforce Analytics",
    },
    {
        "term": "Overtime",
        "definition": "Hours worked beyond scheduled shift, captured in attendance or payroll attendance lines.",
        "formula": "SUM(total_ot_hours) or SUM(overtime_pay)",
        "owner": "Workforce Analytics",
    },
    {
        "term": "Payroll",
        "definition": "Processed salary outputs from the MintHRM payroll engine (not recalculated in the warehouse).",
        "formula": "TBD",
        "owner": "Payroll",
    },
    {
        "term": "Gross Salary",
        "definition": "Total earnings before deductions for a pay period.",
        "formula": "SUM(gross_salary) from fct_processed_salary",
        "owner": "Payroll",
    },
    {
        "term": "Net Salary",
        "definition": "Take-home pay after tax and other deductions for a pay period.",
        "formula": "SUM(net_salary) from fct_processed_salary",
        "owner": "Payroll",
    },
    {
        "term": "Department",
        "definition": "Organizational unit assigned to an employee, derived from org hierarchy or designation.",
        "formula": "TBD — department_name on dim_employee",
        "owner": "HR Analytics",
    },
    {
        "term": "Designation",
        "definition": "Job title or role assigned to an employee.",
        "formula": "TBD — designation_name on dim_employee",
        "owner": "HR Analytics",
    },
    {
        "term": "Cost Center",
        "definition": "Financial attribution unit for employee cost; sourced from employment attributes when available.",
        "formula": "TBD",
        "owner": "Finance",
    },
    {
        "term": "Turnover Rate",
        "definition": "Rate at which employees leave the organization over a period.",
        "formula": "TBD — vw_turnover / lifecycle facts",
        "owner": "HR Analytics",
    },
    {
        "term": "Absenteeism",
        "definition": "Rate or count of unplanned absence days relative to scheduled work days.",
        "formula": "days_absent / (days_present + days_absent) from mart_attendance_monthly_summary",
        "owner": "Workforce Analytics",
    },
    {
        "term": "FTE",
        "definition": "Full-time equivalent headcount; not explicitly modeled — TBD if fractional FTE is required.",
        "formula": "TBD",
        "owner": "HR Analytics",
    },
]

METRICS: list[dict[str, str]] = [
    {
        "metric": "Headcount",
        "description": "Current active workforce at month-end.",
        "formula": "SUM(active_headcount)",
        "filters": "snapshot_month = reporting month",
        "source": "vw_headcount / mart_headcount_monthly",
        "aggregation": "SUM",
        "business_owner": "HR",
    },
    {
        "metric": "Joiners",
        "description": "Employees who joined in the reporting period.",
        "formula": "COUNT lifecycle join events",
        "filters": "event_category = join; effective_date in period",
        "source": "fct_lifecycle_event / vw_lifecycle_summary",
        "aggregation": "COUNT",
        "business_owner": "HR",
    },
    {
        "metric": "Leavers",
        "description": "Employees who left in the reporting period.",
        "formula": "COUNT lifecycle exit events",
        "filters": "resignation/termination events in period",
        "source": "fct_lifecycle_event / vw_turnover",
        "aggregation": "COUNT",
        "business_owner": "HR",
    },
    {
        "metric": "Turnover Rate",
        "description": "Leavers relative to average headcount in period.",
        "formula": "TBD",
        "filters": "TBD",
        "source": "vw_turnover",
        "aggregation": "TBD",
        "business_owner": "HR",
    },
    {
        "metric": "Absenteeism Rate",
        "description": "Share of scheduled days marked absent.",
        "formula": "SUM(days_absent) / NULLIF(SUM(days_present + days_absent), 0)",
        "filters": "mart_attendance_monthly_summary",
        "source": "vw_attendance_summary",
        "aggregation": "Ratio",
        "business_owner": "Workforce",
    },
    {
        "metric": "Leave Utilization",
        "description": "Approved leave days used relative to entitlement.",
        "formula": "approved_leave_days / total_entitled_days",
        "filters": "vw_leave_utilization when available",
        "source": "vw_leave_utilization / mart_leave_monthly_summary",
        "aggregation": "Ratio",
        "business_owner": "HR",
    },
    {
        "metric": "Overtime Hours",
        "description": "Total overtime hours in period.",
        "formula": "SUM(total_overtime_hours)",
        "filters": "year_month in period",
        "source": "mart_attendance_monthly_summary / vw_attendance_summary",
        "aggregation": "SUM",
        "business_owner": "Workforce",
    },
    {
        "metric": "Gross Payroll",
        "description": "Total gross pay for processed payroll runs.",
        "formula": "SUM(gross_salary)",
        "filters": "process_status = processed",
        "source": "fct_processed_salary / vw_payroll_summary",
        "aggregation": "SUM",
        "business_owner": "Payroll",
    },
    {
        "metric": "Net Payroll",
        "description": "Total net pay for processed payroll runs.",
        "formula": "SUM(net_salary)",
        "filters": "process_status = processed",
        "source": "fct_processed_salary / vw_payroll_summary",
        "aggregation": "SUM",
        "business_owner": "Payroll",
    },
    {
        "metric": "Department Headcount",
        "description": "Active employees grouped by department.",
        "formula": "COUNT(employee_sk) GROUP BY department_name",
        "filters": "is_current = true AND emp_status = 'active'",
        "source": "dim_employee / mart_employee_current",
        "aggregation": "COUNT",
        "business_owner": "HR",
    },
    {
        "metric": "Gender Ratio",
        "description": "Distribution of employees by gender.",
        "formula": "COUNT by gender / total COUNT",
        "filters": "active employees",
        "source": "mart_employee_current",
        "aggregation": "Ratio",
        "business_owner": "HR",
    },
    {
        "metric": "Average Tenure",
        "description": "Mean years of service for active employees.",
        "formula": "AVG(tenure_years)",
        "filters": "mart_employee_current",
        "source": "mart_employee_current",
        "aggregation": "AVG",
        "business_owner": "HR",
    },
]

DEFAULT_GOVERNANCE: dict[str, str] = {
    "data_owner": "HR Analytics",
    "technical_owner": "Data Engineering",
    "classification": "Internal",
    "retention": "7 years",
}

DOMAIN_GOVERNANCE: dict[str, dict[str, str]] = {
    "Payroll": {**DEFAULT_GOVERNANCE, "data_owner": "Payroll"},
    "Leave Management": {**DEFAULT_GOVERNANCE, "data_owner": "HR Operations"},
    "Workforce": DEFAULT_GOVERNANCE,
    "Attendance": {**DEFAULT_GOVERNANCE, "data_owner": "Workforce Analytics"},
}

PII_COLUMN_PATTERNS: tuple[str, ...] = (
    "email",
    "phone",
    "mob",
    "nic",
    "national_id",
    "passport",
    "date_of_birth",
    "dob",
    "bank_acc",
    "account_no",
    "acc_no",
    "passbook",
)

SENSITIVE_COLUMN_PATTERNS: tuple[str, ...] = (
    "salary",
    "basic_salary",
    "net_salary",
    "gross_salary",
    "tax",
    "epf",
    "etf",
    "bank_amount",
)

DATA_QUALITY_RULES: list[dict[str, str]] = [
    {
        "rule": "Employee surrogate key uniqueness",
        "validation": "COUNT(DISTINCT employee_sk) = COUNT(*) on dim_employee versions",
        "scope": "dim_employee",
    },
    {
        "rule": "One current employee version",
        "validation": "At most one is_current = true per tenant_id, source_system, source_emp_id",
        "scope": "dim_employee",
    },
    {
        "rule": "No future birth dates",
        "validation": "date_of_birth <= CURRENT_DATE OR date_of_birth IS NULL",
        "scope": "dim_employee",
    },
    {
        "rule": "Leave end date after start date",
        "validation": "end_date >= start_date",
        "scope": "fct_leave_application",
    },
    {
        "rule": "Leave days non-negative",
        "validation": "requested_days >= 0 AND approved_days >= 0",
        "scope": "fct_leave_application",
    },
    {
        "rule": "Processed salary grain uniqueness",
        "validation": "UNIQUE(tenant_id, source_system, source_processed_salary_id)",
        "scope": "fct_processed_salary",
    },
    {
        "rule": "Payroll net not greater than gross",
        "validation": "net_salary <= gross_salary (flag exceptions)",
        "scope": "fct_processed_salary",
    },
]

AI_VIEW_METADATA: dict[str, dict[str, object]] = {
    "vw_headcount": {
        "aliases": ["headcount", "workforce size", "staff count", "employee count"],
        "questions": [
            "How many active employees do we have?",
            "Headcount by month",
            "Workforce trend",
        ],
        "dimensions": ["snapshot_month", "legal_entity"],
        "measures": ["active_headcount"],
    },
    "vw_payroll_summary": {
        "aliases": ["payroll", "salary", "compensation", "payslip"],
        "questions": [
            "Total gross payroll this month",
            "Net pay by department",
            "Payroll summary by period",
        ],
        "dimensions": ["period_label", "department_name", "legal_entity"],
        "measures": ["gross_salary", "net_salary", "total_deductions"],
    },
    "vw_attendance_summary": {
        "aliases": ["attendance", "absence", "punctuality", "overtime"],
        "questions": [
            "Absenteeism rate by department",
            "Overtime hours this month",
            "Late arrivals trend",
        ],
        "dimensions": ["year_month", "department_name"],
        "measures": ["days_absent", "days_present", "total_overtime_hours"],
    },
    "vw_leave_summary": {
        "aliases": ["leave", "time off", "vacation", "sick leave"],
        "questions": [
            "Leave days taken by type",
            "Leave balance summary",
        ],
        "dimensions": ["leave_type_name", "period_label"],
        "measures": ["days_taken", "balance_days"],
    },
    "vw_employee_leave_history": {
        "aliases": ["leave history", "leave applications", "time off requests"],
        "questions": [
            "Show leave history for an employee",
            "Pending leave applications",
        ],
        "dimensions": ["department_name", "leave_type", "leave_status"],
        "measures": ["approved_days", "requested_days"],
    },
    "vw_current_leave_balance": {
        "aliases": ["leave balance", "remaining leave", "entitlement"],
        "questions": [
            "Current leave balance by employee",
            "Remaining annual leave",
        ],
        "dimensions": ["department_name", "leave_type"],
        "measures": ["remaining_days", "entitled_days", "used_days"],
    },
    "vw_leave_liability": {
        "aliases": ["leave liability", "expiring leave", "paid leave balance"],
        "questions": [
            "Leave liability by department",
            "Leave expiring in 90 days",
        ],
        "dimensions": ["department_name", "leave_type"],
        "measures": ["liability_days"],
    },
    "vw_leave_utilization": {
        "aliases": ["leave utilization", "leave usage rate"],
        "questions": [
            "Leave utilization by department",
            "Used vs entitled leave",
        ],
        "dimensions": ["year_month", "department_name", "leave_type"],
        "measures": ["utilization_rate_pct", "approved_leave_days"],
    },
    "vw_turnover": {
        "aliases": ["turnover", "attrition", "leavers"],
        "questions": ["Turnover rate", "Who left this quarter?"],
        "dimensions": ["department_name", "period"],
        "measures": ["TBD"],
    },
    "vw_lifecycle_summary": {
        "aliases": ["lifecycle", "joiners", "promotions", "transfers"],
        "questions": ["Joiners this month", "Promotions by department"],
        "dimensions": ["event_category", "department_name"],
        "measures": ["event_count"],
    },
    "vw_employment_monthly": {
        "aliases": ["employment snapshot", "monthly employment"],
        "questions": ["Employment state at month end"],
        "dimensions": ["snapshot_month", "designation"],
        "measures": ["headcount"],
    },
    "vw_salary_bands": {
        "aliases": ["salary bands", "compensation bands", "pay ranges"],
        "questions": ["Average salary by grade", "Headcount by salary band"],
        "dimensions": ["grade_name", "designation_name", "legal_entity"],
        "measures": ["avg_salary", "headcount"],
    },
    "vw_pending_leave_approvals": {
        "aliases": ["pending approvals", "leave approval queue"],
        "questions": ["Leaves waiting for approval"],
        "dimensions": ["department_name", "leave_type"],
        "measures": ["pending_count"],
    },
    "vw_performance_summary": {
        "aliases": ["performance", "appraisal", "review scores"],
        "questions": ["Performance ratings summary"],
        "dimensions": ["TBD"],
        "measures": ["TBD"],
    },
}
