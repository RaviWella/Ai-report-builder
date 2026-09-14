"""
Table-scoped column allowlist helpers (warehouse introspection → SQL validation).

Prevents a common failure mode: binding allowed ``full_name`` because *some other*
grounded table has that column while the query only reads ``vw_payroll_summary``.
"""
from __future__ import annotations

import re
from typing import Optional

from ..schema_broker import SchemaGrounding

# LLM / catalog shorthand → physical column when the target table uses different names.
_TABLE_COLUMN_ALIASES: dict[str, dict[str, str]] = {
    "mart_employee_current": {
        "full_name": "emp_fullname",
        "employee_name": "emp_fullname",
        "name": "emp_fullname",
        "employee_no": "emp_no",
        "employee_number": "emp_no",
        "employee_id": "emp_no",
        "emp_id": "emp_no",
        "designation_name": "designation",
        "job_title_name": "designation",
        "branch_name": "location_name",
        "department_name": "designation_department",
        "manager_emp_no": "superior_emp_no",
        "manager_name": "superior_fullname",
        "reporting_manager": "superior_fullname",
        "reporting_manager_name": "superior_fullname",
        "employment_category": "employee_category",
        "employment_type": "employee_category",
        "category": "employee_category",
        "payroll_group_name": "payroll_group",
        "company_name": "legal_entity",
        "designation_id": "designation",
        "org_unit_name": "emp_position",
    },
    "vw_payroll_summary": {
        "full_name": "emp_fullname",
        "employee_name": "emp_fullname",
        "name": "emp_fullname",
        "employee_no": "emp_no",
        "employee_number": "emp_no",
        "employee_id": "employee_sk",
        "branch_name": "branch",
        "location_name": "branch",
        "department_name": "department_id",
        "pay_frequency": "payroll_frequency",
        "pay_period": "period_label",
        "payroll_period": "period_label",
    },
    "mart_processed_payroll_summary": {
        "employee_no": "emp_no",
        "employee_number": "emp_no",
        "employee_name": "emp_fullname",
        "full_name": "emp_fullname",
        "payroll_group": "payroll_group_name",
    },
    "fct_processed_salary": {
        "employee_id": "employee_sk",
        "emp_id": "employee_sk",
        "payroll_period_id": "payroll_period_sk",
    },
    "fct_processed_add_ded": {
        "employee_id": "employee_sk",
        "payroll_period_id": "payroll_period_sk",
    },
    "fct_processed_tax": {
        "employee_id": "employee_sk",
        "payroll_period_id": "payroll_period_sk",
    },
    "fct_processed_loan_deduction": {
        "employee_id": "employee_sk",
        "payroll_period_id": "payroll_period_sk",
    },
    "fct_variable_pay_item": {
        "employee_id": "employee_sk",
    },
    "fact_leave_transaction": {
        "status": "leave_status_name",
        "approval_status": "leave_status_name",
        "leave_status": "leave_status_name",
        "type": "leave_type_id",
        "leave_type": "leave_type_id",
        "employee_id": "employee_sk",
        "emp_id": "employee_sk",
    },
    "fact_leave_balance": {
        "employee_id": "employee_sk",
        "leave_days": "days_approved",
        "leave_status": "days_approved",
    },
    "mart_headcount_monthly": {
        "active_count": "active_headcount",
        "year_month": "snapshot_month",
        "new_hires": "active_headcount",
        "separations": "resigned_headcount_eom",
    },
    "fct_overtime": {
        "employee_id": "employee_sk",
        "overtime_hours": "total_ot_hours",
    },
    "fct_salary_change": {
        "old_basic_salary": "previous_salary",
        "new_basic_salary": "new_salary",
        "change_date": "effective_date",
    },
    "dim_canonical_pay_item": {
        "pay_item_name": "canonical_item_name",
        "pay_item_type": "item_type",
        "pay_item_sk": "canonical_pay_item_sk",
    },
    "fct_processed_add_ded": {
        "pay_item_sk": "canonical_pay_item_sk",
    },
    "vw_performance_summary": {
        "employee_sk": "employee_id",
        "rating_bucket": "status",
        "review_cycle": "period_label",
        "department_name": "department_id",
    },
    "vw_salary_bands": {
        "band_name": "grade_name",
        "band_min": "min_salary",
        "band_max": "max_salary",
    },
    "vw_leave_summary": {
        "employee_no": "emp_no",
        "employee_id": "employee_sk",
    },
    "fct_daily_attendance": {
        "employee_id": "employee_sk",
    },
    "vw_attendance_summary": {
        "employee_id": "employee_sk",
        "employee_no": "emp_no",
        "period_label": "month",
        "period_date": "month",
        "late_events": "late_count",
        "branch_name": "branch_id",
        "department_name": "department_id",
        "absent_days": "scheduled_days",
    },
    "mart_attendance_monthly_summary": {
        "employee_id": "employee_sk",
        "employee_no": "emp_no",
        "present_days": "days_present",
        "absent_days": "days_absent",
        "late_events": "days_late",
        "period_label": "year_month",
        "month": "year_month",
    },
    "dim_payroll_period": {
        "period_start": "period_end_date",
        "period_label": "period_end_date",
    },
    "vw_lifecycle_summary": {
        "event_month": "period_label",
        "event_date": "effective_date",
    },
    "fct_lifecycle_event": {
        "employee_id": "employee_sk",
        "event_type": "event_category",
        "event_reason": "reason",
        "event_date": "effective_date",
    },
    "vw_turnover": {
        "department_name": "department_id",
    },
    "vw_headcount": {
        "department_name": "department_id",
    },
    "fct_salary_change": {
        "employee_id": "employee_sk",
    },
    "fct_overtime": {
        "employee_id": "employee_sk",
    },
    "dim_leave_type": {
        "type": "leave_type_name",
        "leave_type": "leave_type_name",
    },
    "dim_payroll_group": {
        "pay_group": "payroll_group_name",
        "pay_group_name": "payroll_group_name",
    },
    "dim_employee": {
        "employee_name": "emp_fullname",
        "emp_name": "emp_fullname",
        "employee_number": "emp_no",
        "employee_no": "emp_no",
    },
    "fct_salary_bank_instruction": {
        "employee_id": "employee_sk",
        "emp_id": "employee_sk",
        "bank_id": "source_bank_id",
    },
    "dim_bank": {
        "bank_id": "source_bank_id",
    },
}


def columns_by_table_short(grounding: SchemaGrounding) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for qualified, cols in grounding.columns_by_table.items():
        short = qualified.rsplit(".", 1)[-1].lower()
        out.setdefault(short, set()).update(c.lower() for c in cols if c)
    return out


def allowed_columns_for_table(
    grounding: SchemaGrounding,
    table_short: str,
) -> set[str]:
    return columns_by_table_short(grounding).get((table_short or "").lower(), set())


def resolve_column_for_table(
    bad_column: str,
    table_short: str,
    grounding: SchemaGrounding,
) -> Optional[str]:
    """Return a physical column on ``table_short`` to replace ``bad_column``, or None."""
    bad = (bad_column or "").strip().lower()
    short = (table_short or "").strip().lower()
    if not bad or not short:
        return None

    allowed = allowed_columns_for_table(grounding, short)
    if bad in allowed:
        return bad

    alias_map = _TABLE_COLUMN_ALIASES.get(short, {})
    mapped = alias_map.get(bad)
    if mapped and mapped in allowed:
        return mapped

    for candidate in sorted(allowed):
        if bad in candidate or candidate.endswith(bad):
            return candidate
    return None


def try_rewrite_unknown_columns(
    sql: str,
    grounding: SchemaGrounding,
    *,
    referenced_shorts: Optional[set[str]] = None,
) -> Optional[str]:
    """
    Deterministically replace known bad column refs using per-table allowlists.

    Rewrites qualified and unqualified ``Column`` nodes (SELECT, WHERE, ORDER BY, …).
    """
    import sqlglot
    from sqlglot import exp

    if not grounding.columns_by_table or not sql.strip():
        return None

    try:
        tree = sqlglot.parse_one(sql, dialect="postgres")
    except Exception:  # noqa: BLE001
        return None

    alias_to_short: dict[str, str] = {}
    for table in tree.find_all(exp.Table):
        short = (table.name or "").lower()
        if not short:
            continue
        alias = (table.alias_or_name or table.name or "").lower()
        alias_to_short[alias] = short
        if table.name:
            alias_to_short[table.name.lower()] = short

    refs = referenced_shorts or set(alias_to_short.values())
    if not refs:
        return None

    replacements: list[tuple[str, str, str]] = []
    for col in tree.find_all(exp.Column):
        col_name = (col.name or "").lower()
        if not col_name or col_name == "*":
            continue
        table_ref = (col.table or "").lower()
        if table_ref:
            table_short = alias_to_short.get(table_ref, table_ref)
        elif len(refs) == 1:
            table_short = next(iter(refs))
        else:
            matches = [
                t for t in refs if col_name in allowed_columns_for_table(grounding, t)
            ]
            if len(matches) != 1:
                continue
            table_short = matches[0]

        allowed = allowed_columns_for_table(grounding, table_short)
        if col_name in allowed:
            continue

        replacement = resolve_column_for_table(col_name, table_short, grounding)
        if not replacement or replacement == col_name:
            continue

        if table_ref:
            replacements.append((f"{table_ref}.{col_name}", f"{table_ref}.{replacement}", ""))
        else:
            replacements.append((col_name, replacement, r"\b"))

    if not replacements:
        return None

    out = sql
    changed = False
    for old, new, wrap in replacements:
        if wrap:
            pattern = rf"\b{re.escape(old)}\b"
        else:
            pattern = rf"\b{re.escape(old)}\b"
        nxt = re.sub(pattern, new, out, count=0, flags=re.IGNORECASE)
        if nxt != out:
            out = nxt
            changed = True

    return out if changed else None
