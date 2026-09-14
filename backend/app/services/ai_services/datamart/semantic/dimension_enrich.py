"""Dimension enrichment for schema grounding.

Problem:
- The schema broker may return a minimal table set (often 1 table) to reduce noise.
- The LLM then generates single-table SQL, sometimes projecting `*_id`/`*_sk` identifiers
  without joining to the dimension table that holds human-readable labels.

Solution:
- After warehouse column introspection, inspect grounded tables for join-key columns.
- If the user question implies a human-readable label, automatically include the
  corresponding `dim_*` table(s) in the grounded allowlist, so the LLM can safely JOIN.
- For multi-table topics (bank, employment category, shifts), include required fact/dim
  tables even when the initial broker packet is only `dim_employee`.

This module intentionally uses conservative heuristics to avoid exploding table counts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..schema_broker import SchemaGrounding, ensure_grounding_includes_tables


@dataclass(frozen=True)
class _DimRule:
    """Rule mapping join keys → dimension tables when user asks for labels."""

    keys: tuple[str, ...]
    dim_table_short: str
    # keywords that indicate user wants readable labels for this dimension
    intent_keywords: tuple[str, ...]
    require_keys: bool = True


@dataclass(frozen=True)
class _TopicRule:
    """Always include these tables when the question matches (multi-table reports)."""

    intent_keywords: tuple[str, ...]
    tables: tuple[str, ...]


_RULES: tuple[_DimRule, ...] = (
    # Employee labels: prefer the current mart for names/branch/designation labels.
    _DimRule(
        keys=("employee_sk", "employee_id", "employee_no", "emp_no"),
        dim_table_short="mart_employee_current",
        intent_keywords=("employee", "employees", "staff", "workforce", "roster", "list"),
    ),
    _DimRule(
        keys=("designation_id", "designation_sk", "source_desig_id"),
        dim_table_short="dim_designation",
        intent_keywords=("designation", "job title", "title", "role", "grade", "position"),
    ),
    _DimRule(
        keys=("org_unit_id", "org_unit_sk", "branch_id", "department_id"),
        dim_table_short="dim_org_unit",
        intent_keywords=("branch", "department", "org unit", "orgunit", "organization unit", "team"),
    ),
    _DimRule(
        keys=("leave_type_id",),
        dim_table_short="dim_leave_type",
        intent_keywords=("leave type", "leave category", "leave"),
    ),
    _DimRule(
        keys=("payroll_group_id", "payroll_group_sk", "pay_group_id"),
        dim_table_short="dim_pay_group",
        intent_keywords=("pay group", "payroll group", "pay group name", "payroll group name"),
    ),
    _DimRule(
        keys=("job_id",),
        dim_table_short="dim_job",
        intent_keywords=("job", "position", "requisition", "vacancy"),
    ),
    _DimRule(
        keys=("candidate_id",),
        dim_table_short="dim_candidate",
        intent_keywords=("candidate", "recruitment", "hiring"),
    ),
)

_TOPIC_RULES: tuple[_TopicRule, ...] = (
    _TopicRule(
        intent_keywords=(
            "bank",
            "bank details",
            "bank code",
            "bank name",
            "account number",
            "passbook",
            "salary bank",
        ),
        tables=(
            "dim_bank",
            "dim_bank_branch",
            "fct_salary_bank_instruction",
            "mart_employee_current",
            "dim_employee",
        ),
    ),
    _TopicRule(
        intent_keywords=(
            "employment category",
            "employment type",
            "emp category",
            "employee category",
        ),
        tables=("mart_employee_current",),
    ),
    _TopicRule(
        intent_keywords=(
            "employment snapshot",
            "employment monthly",
            "employment history",
            "employment status history",
        ),
        tables=(
            "fct_employment_snapshot",
            "vw_employment_monthly",
            "mart_employee_current",
            "dim_employee",
        ),
    ),
    _TopicRule(
        intent_keywords=("shift", "shifts", "shift assignment", "roster shift"),
        tables=(
            "dim_shift",
            "fct_employment_snapshot",
            "mart_employee_current",
            "dim_employee",
        ),
    ),
    _TopicRule(
        intent_keywords=(
            "highest paid",
            "top paid",
            "top 10",
            "salary",
            "basic salary",
            "compensation",
            "payroll",
            "ctc",
            "cost to company",
        ),
        tables=(
            "mart_cost_to_company",
            "mart_processed_payroll_summary",
            "vw_payroll_summary",
            "mart_employee_current",
        ),
    ),
    _TopicRule(
            "pay slip",
            "gross pay",
            "net pay",
            "payroll summary",
            "salary for",
            "epf",
            "etf",
            "tax deduction",
            "pay period",
        ),
        tables=(
            "vw_payroll_summary",
            "mart_processed_payroll_summary",
            "dim_payroll_group",
            "dim_payroll_period",
            "mart_employee_current",
        ),
    ),
    _TopicRule(
        intent_keywords=(
            "allowance",
            "deduction",
            "pay item",
            "addition",
            "pay component",
            "variable pay",
        ),
        tables=(
            "fct_processed_add_ded",
            "fct_variable_pay_item",
            "mart_processed_payroll_summary",
            "mart_employee_current",
        ),
    ),
    _TopicRule(
        intent_keywords=(
            "leave application",
            "leave transaction",
            "leave request",
            "annual leave",
            "sick leave",
            "leave taken",
            "leave days",
        ),
        tables=(
            "fact_leave_balance",
            "vw_leave_summary",
            "mart_employee_current",
        ),
    ),
    _TopicRule(
        intent_keywords=(
            "leave balance",
            "leave entitlement",
            "leave remaining",
        ),
        tables=(
            "fact_leave_balance",
            "vw_leave_summary",
            "mart_employee_current",
        ),
    ),
    _TopicRule(
        intent_keywords=(
            "attendance",
            "present days",
            "absent",
            "late",
            "overtime hours",
            "ot hours",
            "punch",
            "timesheet",
        ),
        tables=(
            "vw_attendance_summary",
            "mart_attendance_monthly_summary",
            "fct_daily_attendance",
            "mart_employee_current",
        ),
    ),
    _TopicRule(
        intent_keywords=(
            "probation",
            "probation due",
            "on probation",
        ),
        tables=("mart_employee_current",),
    ),
    _TopicRule(
        intent_keywords=(
            "attrition",
            "turnover",
            "separation",
            "resignation",
            "terminated",
            "exit",
        ),
        tables=(
            "vw_turnover",
            "fct_lifecycle_event",
            "vw_headcount",
            "mart_employee_current",
        ),
    ),
    _TopicRule(
        intent_keywords=(
            "salary increment",
            "salary change",
            "pay revision",
            "increment",
        ),
        tables=(
            "fct_salary_change",
            "mart_employee_current",
        ),
    ),
    _TopicRule(
        intent_keywords=(
            "loan",
            "loan deduction",
            "loan installment",
        ),
        tables=(
            "fct_processed_loan_deduction",
            "mart_processed_payroll_summary",
            "mart_employee_current",
        ),
    ),
    _TopicRule(
        intent_keywords=(
            "overtime",
            "ot request",
            "approved ot",
        ),
        tables=(
            "fct_overtime",
            "mart_employee_current",
            "vw_attendance_summary",
        ),
    ),
)


def _question_matches_keywords(question: str, keywords: tuple[str, ...]) -> bool:
    q = (question or "").lower()
    return any(kw in q for kw in keywords)


def _question_wants_dimension(question: str, rule: _DimRule) -> bool:
    return _question_matches_keywords(question, rule.intent_keywords)


def _grounding_has_any_key(grounding: SchemaGrounding, keys: tuple[str, ...]) -> bool:
    keys_l = {k.lower() for k in keys}
    for cols in (grounding.columns_by_table or {}).values():
        if any((c or "").strip().lower() in keys_l for c in cols):
            return True
    return False


def enrich_grounding_with_dimensions(
    grounding: SchemaGrounding,
    *,
    question: str,
) -> SchemaGrounding:
    """Add dimension tables when join keys are present and the question implies labels."""
    if not grounding.columns_by_table:
        return grounding

    # Only enrich on label-ish questions, not on pure ID requests.
    q_lower = (question or "").lower()
    if re.search(r"\b(id|sk|surrogate|key)\b", q_lower) and not re.search(
        r"\bbank\b|\bemployment\b|\bcategory\b|\bshift\b", q_lower
    ):
        return grounding

    want: list[str] = []

    for topic in _TOPIC_RULES:
        if _question_matches_keywords(question, topic.intent_keywords):
            want.extend(topic.tables)

    for rule in _RULES:
        if not _question_wants_dimension(question, rule):
            continue
        if rule.require_keys and not _grounding_has_any_key(grounding, rule.keys):
            continue
        want.append(rule.dim_table_short)

    if not want:
        return grounding

    expanded = ensure_grounding_includes_tables(grounding, want)
    return expanded if expanded.columns_by_table else grounding
