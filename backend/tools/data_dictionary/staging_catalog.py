"""MintHRM staging table → source system catalog for data dictionary enrichment."""

from __future__ import annotations

from typing import Any

# stg_* / raw_* → sources (MintHRM physical tables) and human description.
STAGING_SOURCE_CATALOG: dict[str, dict[str, Any]] = {
    "stg_branches": {
        "sources": ["branch"],
        "description": "Branch/location master from MintHRM branch (br_id, br_name).",
    },
    "stg_departments": {
        "sources": ["company_hierarchy", "VW_MINT_EMP_DEPARTMENT"],
        "description": "Organization units from company_hierarchy; fallback distinct departments from VW_MINT_EMP_DEPARTMENT.",
    },
    "stg_company_hierarchy_individual": {
        "sources": ["company_hierarchy_individual"],
        "description": "Per-employee org-chart node; ref_emp_id and parent_id (manager link).",
    },
    "stg_designations": {
        "sources": ["hr_designation"],
        "description": "Job titles and grades from hr_designation (desig_id, designation).",
    },
    "stg_employees": {
        "sources": ["hr_empbasic", "hr_employment", "hr_empcontact"],
        "description": "Employee master extract from hr_empbasic with employment and contact enrichment.",
    },
    "stg_attendance": {
        "sources": ["HR_ATTEDANCE"],
        "description": "Daily attendance punches and worked hours from HR_ATTEDANCE.",
    },
    "stg_lifecycle": {
        "sources": ["hr_lifecycle", "hr_lifecycle_position"],
        "description": "Career lifecycle events (hire, transfer, promotion, exit) from hr_lifecycle.",
    },
    "stg_leave_requests": {
        "sources": ["hr_leaveapplication"],
        "description": "Standard leave applications from hr_leaveapplication.",
    },
    "stg_leave_application_dates": {
        "sources": ["hr_leaveapplication_dates"],
        "description": "Leave day-level breakdown from hr_leaveapplication_dates.",
    },
    "stg_leave_types": {
        "sources": ["hr_leavetype"],
        "description": "Leave type definitions from hr_leavetype.",
    },
    "stg_leave_reason": {
        "sources": ["hr_predefine_leave_purpose"],
        "description": "Predefined leave purposes from hr_predefine_leave_purpose.",
    },
    "stg_leave_balance": {
        "sources": ["hr_leave_balance"],
        "description": "Leave balance snapshots from hr_leave_balance.",
    },
    "stg_leave_entitlement": {
        "sources": ["prl_leaveentitle"],
        "description": "Leave entitlement rows from prl_leaveentitle.",
    },
    "stg_leave_approvals": {
        "sources": ["hr_leaveapplication_superiors"],
        "description": "Leave approval workflow actions from hr_leaveapplication_superiors.",
    },
    "stg_short_leave": {
        "sources": ["hr_short_leave"],
        "description": "Short-leave requests from hr_short_leave.",
    },
    "stg_lieu_leave": {
        "sources": ["hr_lieu_leave"],
        "description": "Lieu (compensatory) leave applications from hr_lieu_leave.",
    },
    "stg_lieu_leave_entitlement": {
        "sources": ["lieu_leave_entitlement_data"],
        "description": "Earned lieu-leave entitlements from lieu_leave_entitlement_data.",
    },
    "stg_maternity_leave": {
        "sources": ["hr_leave_maternity"],
        "description": "Maternity leave applications from hr_leave_maternity.",
    },
    "stg_leave_planner": {
        "sources": ["hr_leave_planner", "hr_leave_planner_dates"],
        "description": "Planned leave from hr_leave_planner (day types in hr_leave_planner_dates).",
    },
    "stg_performance_reviews": {
        "sources": ["(PM module — placeholder)"],
        "description": "Performance review staging placeholder until PM source tables are wired in ETL.",
    },
    "stg_training_records": {
        "sources": ["(training module — placeholder)"],
        "description": "Training record staging placeholder until training source tables are mapped in ETL.",
    },
    "raw_hr_payroll_groups": {
        "sources": ["hr_payroll_groups"],
        "description": "Raw payroll group definitions from hr_payroll_groups.",
    },
    "stg_hr_payroll_groups": {
        "sources": ["hr_payroll_groups"],
        "description": "Payroll group master view from hr_payroll_groups.",
    },
    "stg_bank": {
        "sources": ["bank"],
        "description": "Bank master (payroll) from MintHRM bank table.",
    },
    "stg_mas_branch": {
        "sources": ["mas_branch"],
        "description": "Bank branch master from mas_branch (linked to bank).",
    },
    # dbt-normalized payroll staging views (hr_raw)
    "stg_processed_sal_basic_data": {
        "sources": ["processed_sal_basic_data"],
        "description": "Normalized processed salary snapshot lines (engine output; lands in stg_payroll_details).",
    },
    "stg_processed_sal_add_ded": {
        "sources": ["processed_sal_add_ded"],
        "description": "Processed add/deduction lines per employee and payroll group.",
    },
    "stg_processed_sal_attendance": {
        "sources": ["processed_sal_attendance"],
        "description": "Attendance amounts included in processed payroll.",
    },
    "stg_processed_sal_attendance_compliance": {
        "sources": ["processed_sal_attendance_compliance"],
        "description": "Statutory attendance compliance amounts in processed payroll.",
    },
    "stg_processed_sal_basic_data_compliance": {
        "sources": ["processed_sal_basic_data_compliance"],
        "description": "Statutory basic salary compliance slice from payroll engine.",
    },
    "stg_processed_tax_data": {
        "sources": ["processed_tax_data_for_employee"],
        "description": "Processed tax lines per employee from processed_tax_data_for_employee.",
    },
    "stg_processed_loan_data": {
        "sources": ["processed_loan_data"],
        "description": "Processed loan master rows from processed_loan_data.",
    },
    "stg_processed_installment_payment_data": {
        "sources": ["processed_installment_payment_data"],
        "description": "Loan installment payment lines from processed_installment_payment_data.",
    },
    "stg_processed_loan_deduction": {
        "sources": ["processed_loan_data", "processed_installment_payment_data"],
        "description": "Unified loan deduction staging (loan + installment union for dbt).",
    },
    "stg_processed_multi_currency_for_emp_sal": {
        "sources": ["processed_multi_currency_for_emp_sal"],
        "description": "Multi-currency salary lines from processed_multi_currency_for_emp_sal.",
    },
    "stg_processed_non_consider_pay_items": {
        "sources": ["processed_non_consider_pay_items"],
        "description": "Non-considered pay items from processed_non_consider_pay_items.",
    },
    "stg_prl_processed_nonecash_benefits": {
        "sources": ["prl_processed_nonecash_benefits"],
        "description": "Processed non-cash benefit lines from prl_processed_nonecash_benefits.",
    },
    "stg_prl_variable_pay_items": {
        "sources": ["prl_variableadditions_forsal", "prl_variabledeductions_forsal"],
        "description": "Variable pay additions and deductions staged for dynamic paysheet pivot.",
    },
    "stg_prl_salary_retrieve": {
        "sources": ["prl_salary_retrieve"],
        "description": "Salary retrieve (pay method setup) rows from prl_salary_retrieve.",
    },
    "stg_prl_salary_bank_data": {
        "sources": ["prl_salary_bank_data"],
        "description": "Salary bank account split rows from prl_salary_bank_data.",
    },
    "stg_payroll_runs": {
        "sources": ["processed_sal_basic_data", "hr_payroll_groups"],
        "description": "Payroll run metadata (period x group) aggregated from processed salary snapshots.",
        "primary_key": "id",
    },
    "stg_payroll_loan_deductions": {
        "sources": ["processed_loan_data", "processed_installment_payment_data"],
        "description": "Loan and installment deduction lines merged for payroll (processed_loan_data + installments).",
        "primary_key": "id",
    },
    "stg_payroll_salary_analyze_data": {
        "sources": ["prl_processed_salary_analyze"],
        "description": "Salary analyze detail rows from prl_processed_salary_analyze.",
        "primary_key": "id",
    },
    "raw_events": {
        "sources": ["(CDC / event stream)"],
        "description": "Raw event landing (source_table identifies originating MintHRM entity).",
        "primary_key": "id",
        "business_key": "source_table, id",
    },
    "raw_processed_sal_basic_data": {
        "sources": ["processed_sal_basic_data"],
        "description": "Raw processed salary snapshot landing (feeds stg_payroll_details / stg_processed_sal_basic_data).",
        "primary_key": "id",
    },
}


def build_staging_catalog(payroll_logical_to_stg: dict[str, str]) -> dict[str, dict[str, Any]]:
    """Merge static catalog with payroll source map (logical MintHRM table → stg_*)."""
    catalog: dict[str, dict[str, Any]] = {
        k: dict(v) for k, v in STAGING_SOURCE_CATALOG.items()
    }
    for logical, stg in payroll_logical_to_stg.items():
        if stg in catalog:
            continue
        if not (stg.startswith("stg_") or stg.startswith("raw_")):
            continue
        catalog[stg] = {
            "sources": [logical],
            "description": f"Payroll engine extract: {logical} → {stg}.",
        }
    return catalog


def apply_staging_catalog_entry(obj: Any, entry: dict[str, Any]) -> None:
    """Apply catalog entry to ObjectInfo (duck-typed)."""
    if entry.get("sources"):
        obj.source_systems = list(entry["sources"])
    if entry.get("description"):
        obj.description = str(entry["description"])
    if entry.get("grain") and getattr(obj, "grain", "TBD") == "TBD":
        obj.grain = str(entry["grain"])
    if entry.get("business_key"):
        obj.business_key = str(entry["business_key"])
    if entry.get("primary_key"):
        obj.primary_key = str(entry["primary_key"])
