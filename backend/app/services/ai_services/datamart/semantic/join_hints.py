"""
Curated join hints for the MintHRM HR datamart.
Used by the schema broker — not sent to the LLM as executable SQL.
"""
from __future__ import annotations

from ..workspace.runtime_context import mart_schema_for_hints

# (left_table_suffix, right_table_suffix, hint template with {S} placeholder)
_RAW_HINT_TEMPLATES: list[tuple[str, str, str]] = [
    (
        "dim_employee",
        "fact_payroll",
        "Join {S}.dim_employee.employee_no = {S}.fact_payroll_detail.employee_no "
        "(payroll detail is keyed by employee_no; employee_id when present on both).",
    ),
    (
        "dim_employee",
        "fact_attendance",
        "Join {S}.dim_employee.employee_id = {S}.fact_attendance.employee_id for attendance facts.",
    ),
    (
        "dim_employee",
        "fact_leave",
        "Join {S}.dim_employee.employee_id = {S}.fact_leave_transaction.employee_id for leave.",
    ),
    (
        "dim_employee",
        "fact_attrition",
        "Join {S}.dim_employee.employee_id = {S}.fact_attrition.employee_id for exits and attrition.",
    ),
    (
        "dim_employee",
        "fact_performance",
        "Join {S}.dim_employee.employee_id = {S}.fact_performance_review.employee_id for reviews.",
    ),
    (
        "dim_employee",
        "fact_employee_snapshot",
        "Join {S}.dim_employee.employee_id = {S}.fact_employee_snapshot.employee_id for historical snapshots.",
    ),
    (
        "dim_employee",
        "dim_organization",
        "Org attributes may appear on {S}.dim_employee (legal_entity, branch, organization_unit) "
        "or {S}.dim_organization — use columns from the grounded allowlist only.",
    ),
    (
        "dim_employee",
        "dim_designation",
        "Join {S}.dim_employee d to {S}.dim_designation des on "
        "d.source_desig_id = des.source_desig_id for job title (SELECT des.designation_name). "
        "On mart_employee_current, use m.designation directly — do not join des.designation_sk.",
    ),
    (
        "mart_employee_current",
        "dim_employee",
        "Join {S}.mart_employee_current m to {S}.dim_employee d on m.employee_sk = d.employee_sk "
        "for current workforce rows. List reports: m.emp_no, m.emp_fullname, m.employee_category — "
        "not employee_sk or d.employee_id.",
    ),
    (
        "mart_employee_current",
        "fct_salary_bank_instruction",
        "Join {S}.mart_employee_current m to {S}.fct_salary_bank_instruction bi "
        "on m.employee_sk = bi.employee_sk for salary bank accounts. "
        "Then join {S}.dim_bank dbk on dbk.source_bank_id::text = bi.source_bank_id::text "
        "for bank_code and bank_name.",
    ),
    (
        "fct_salary_bank_instruction",
        "dim_bank",
        "Join {S}.fct_salary_bank_instruction bi to {S}.dim_bank dbk "
        "on dbk.source_bank_id::text = bi.source_bank_id::text (cast both sides if types differ).",
    ),
    (
        "fact_recruitment",
        "dim_candidate",
        "Join {S}.fact_recruitment_pipeline.candidate_id = {S}.dim_candidate.candidate_id.",
    ),
    (
        "fact_leave",
        "dim_leave",
        "Use aliases flt (fact_leave_transaction) and dlt (dim_leave_type) — never reuse one alias "
        "for both tables. Join: {S}.fact_leave_transaction flt; "
        "JOIN {S}.dim_leave_type dlt ON flt.leave_type_id::text = dlt.leave_type_id::text.",
    ),
    (
        "mart_employee_current",
        "mart_processed_payroll",
        "Join {S}.mart_employee_current m to {S}.mart_processed_payroll_summary p "
        "on m.employee_sk = p.employee_sk for pay-period salary columns (gross_salary, net_salary, tax).",
    ),
    (
        "mart_employee_current",
        "mart_cost_to_company",
        "Join {S}.mart_employee_current m to {S}.mart_cost_to_company c "
        "on m.employee_sk = c.employee_sk for basic_salary and total_compensation (CTC).",
    ),
    (
        "mart_employee_current",
        "dim_designation",
        "Job title is already on {S}.mart_employee_current as designation — use m.designation "
        "without joining dim_designation unless you need historical designation attributes. "
        "If joining dim_designation, use source_desig_id = source_desig_id (never designation = designation_sk).",
    ),
    (
        "mart_employee_current",
        "vw_payroll_summary",
        "Join {S}.mart_employee_current m to {S}.hr_semantic.vw_payroll_summary v "
        "on m.employee_sk = v.employee_sk for payslip-style listings (emp_no, period_label, net_salary).",
    ),
    (
        "mart_employee_current",
        "vw_attendance",
        "Join {S}.mart_employee_current m to {S}.vw_attendance_summary a "
        "on m.employee_sk = a.employee_sk for present days, late, and OT KPIs.",
    ),
    (
        "mart_employee_current",
        "fact_leave",
        "Join {S}.mart_employee_current m to {S}.fact_leave_transaction flt "
        "on m.employee_sk = flt.employee_sk; add dim_leave_type for leave_type_name.",
    ),
    (
        "mart_employee_current",
        "fct_lifecycle",
        "Join {S}.mart_employee_current m to {S}.fct_lifecycle_event ev "
        "on m.employee_sk = ev.employee_sk for hire/transfer/separation events.",
    ),
    (
        "fct_processed_add_ded",
        "mart_processed_payroll",
        "Join {S}.fct_processed_add_ded ad to {S}.mart_processed_payroll_summary p "
        "on ad.employee_sk = p.employee_sk and ad.payroll_period_sk = p.payroll_period_sk.",
    ),
]

RELATED_TABLE_SUFFIXES: dict[str, list[str]] = {
    "dim_employee": [
        "fact_payroll_detail",
        "fact_attendance",
        "fact_leave_transaction",
        "fact_performance_review",
        "fact_attrition",
        "fact_employee_snapshot",
        "dim_job",
        "dim_organization",
        "mart_employee_current",
    ],
    "fact_payroll_detail": ["dim_employee", "dim_pay_group", "dim_pay_component"],
    "fact_attendance": ["dim_employee", "fact_payroll_detail"],
    "fact_leave_transaction": ["dim_employee", "dim_leave_type"],
    "dim_leave_type": ["fact_leave_transaction"],
    "fact_leave_balance": ["dim_employee"],
    "vw_leave_summary": ["dim_employee"],
    "fact_performance_review": ["dim_employee", "dim_review_cycle", "dim_rating_scale"],
    "dim_review_cycle": ["fact_performance_review"],
    "fact_recruitment_pipeline": [
        "dim_candidate",
        "dim_job",
        "dim_source",
        "dim_org_unit",
    ],
    "dim_org_unit": ["fact_recruitment_pipeline", "mart_employee_current"],
    "dim_candidate": ["fact_recruitment_pipeline"],
    "dim_job": ["fact_recruitment_pipeline", "dim_employee"],
    "fact_attrition": ["dim_employee", "dim_termination_reason"],
    "fact_employee_snapshot": ["dim_employee", "dim_date"],
    "dim_date": ["fact_employee_snapshot", "fact_attendance"],
    "dim_pay_group": ["fact_payroll_detail"],
    "dim_pay_component": ["fact_payroll_detail"],
    "vw_headcount": ["mart_employee_current", "dim_employee"],
    "vw_payroll_summary": ["fact_payroll", "fct_processed_salary"],
    "mart_employee_current": [
        "fct_salary_bank_instruction",
        "dim_bank",
        "dim_bank_branch",
        "dim_employee",
    ],
    "fct_salary_bank_instruction": ["mart_employee_current", "dim_bank", "dim_bank_branch"],
    "dim_bank": ["fct_salary_bank_instruction", "dim_bank_branch"],
    "mart_processed_payroll_summary": [
        "mart_employee_current",
        "vw_payroll_summary",
        "dim_payroll_group",
        "dim_payroll_period",
        "fct_processed_salary",
        "fct_processed_add_ded",
        "fct_processed_tax",
        "fct_processed_loan_deduction",
    ],
    "vw_payroll_summary": ["mart_employee_current", "mart_processed_payroll_summary"],
    "vw_attendance_summary": ["mart_employee_current", "mart_attendance_monthly_summary"],
    "mart_attendance_monthly_summary": ["mart_employee_current", "vw_attendance_summary"],
    "fct_daily_attendance": ["mart_employee_current"],
    "fact_leave_transaction": ["mart_employee_current", "dim_leave_type"],
    "fact_leave_balance": ["mart_employee_current", "dim_leave_type", "vw_leave_summary"],
    "vw_leave_summary": ["mart_employee_current", "fact_leave_balance"],
    "fct_lifecycle_event": ["mart_employee_current", "vw_turnover"],
    "vw_turnover": ["mart_employee_current", "vw_headcount"],
    "vw_headcount": ["mart_employee_current", "vw_turnover"],
    "fct_salary_change": ["mart_employee_current"],
    "fct_overtime": ["mart_employee_current", "vw_attendance_summary"],
    "fct_processed_loan_deduction": ["mart_processed_payroll_summary", "mart_employee_current"],
    "dim_payroll_group": ["mart_processed_payroll_summary", "vw_payroll_summary"],
    "dim_payroll_period": ["mart_processed_payroll_summary"],
}


def related_table_short_names(table_short_names: list[str]) -> list[str]:
    """Tables commonly joined to the given set (suffix substring match)."""
    lowered = [t.lower() for t in table_short_names]
    out: list[str] = []
    seen = {t.lower() for t in table_short_names}
    for name in lowered:
        for key, related in RELATED_TABLE_SUFFIXES.items():
            if key not in name:
                continue
            for r in related:
                if r.lower() not in seen:
                    seen.add(r.lower())
                    out.append(r)
    return out


def join_hints_for_tables(table_short_names: list[str]) -> list[str]:
    """Return join hint lines relevant to the selected table set."""
    s = mart_schema_for_hints()
    lowered = {t.lower() for t in table_short_names}
    out: list[str] = []
    for left, right, template in _RAW_HINT_TEMPLATES:
        if any(left in t for t in lowered) and any(right in t for t in lowered):
            out.append(template.format(S=s))
    if not out and len(lowered) >= 2:
        out.append(
            f"When joining multiple tables, qualify every column as <schema>.<table>.<column> "
            f"(mart tables often under {s}) and use only keys present in the allowlist."
        )
    return out
