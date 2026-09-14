"""
Offline SQL resolve eval (S5): Tier A/B without LLM.

Uses mock grounding from question-bank ``expect_tables`` to probe deterministic
templates and verified SQL — same order as ``sql_resolver`` (minus Tier C).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .. import config as dm_config
from ..orchestration.intent_router import ChatIntent, classify_chat_intent
from ..domain_sql.report_spec import compile_report_spec
from ..validation.report_spec_validate import validate_sql_against_report_spec
from ..domain_sql.report_sql_router import try_build_sql_from_report_spec
from ..schema_broker import SchemaGrounding
from ..sql.sql_fast_path import try_resolve_deterministic_sql
from .domain_classifier import classify_domain
from .link_eval import eval_one_case, load_question_bank
from .verified_query_store import retrieve_verified_sql


@dataclass
class ResolveEvalCaseResult:
    section: str
    question_preview: str
    classified_domain: str
    tier: Optional[str]
    sql_source: Optional[str]
    has_sql: bool
    link_ok: bool
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.link_ok and not self.errors


@dataclass
class ResolveEvalReport:
    total: int
    passed: int
    failed: int
    tier_a: int
    tier_b: int
    unresolved: int
    results: list[ResolveEvalCaseResult] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return self.failed == 0


_DOMAIN_MOCK_COLUMNS: dict[str, dict[str, list[str]]] = {
    "payroll": {
        "vw_payroll_summary": [
            "emp_fullname",
            "emp_no",
            "employee_id",
            "employee_sk",
            "payroll_group_name",
            "branch",
            "basic_salary",
            "gross_salary",
            "total_deductions",
            "net_salary",
            "tax_amount",
            "epf_employee_amount",
            "etf_amount",
            "period_label",
            "run_status",
        ],
        "dim_payroll_group": ["payroll_group_name", "payroll_frequency", "currency_code"],
        "mart_employee_current": ["emp_no", "emp_fullname", "location_name", "basic_salary", "branch_id"],
        "fct_processed_salary": ["gross_salary", "payroll_period_sk", "payroll_group_sk"],
        "fct_processed_tax": ["tax_amount", "employee_sk", "payroll_period_sk"],
        "dim_payroll_period": ["period_end_date", "payroll_period_sk", "payroll_year"],
    },
    "leave": {
        "fact_leave_balance": [
            "employee_sk",
            "leave_type_name",
            "leave_type_code",
            "days_approved",
            "days_entitled",
            "balance_days",
            "period_label",
            "year",
        ],
        "vw_leave_summary": [
            "employee_sk",
            "leave_type_name",
            "days_taken",
            "balance_days",
            "period_label",
        ],
        "mart_employee_current": ["emp_fullname", "emp_no", "location_name", "employee_sk"],
        "dim_leave_type": ["leave_type_name", "leave_type_code"],
    },
    "recruitment": {
        "fct_lifecycle_event": [
            "employee_sk",
            "event_category",
            "event_name",
            "effective_date",
            "approved_date",
            "reason",
        ],
        "mart_employee_current": [
            "emp_fullname",
            "employee_sk",
            "join_date",
            "location_name",
            "employee_category",
            "employment_type",
            "designation",
            "designation_department",
        ],
        "dim_employee": ["employee_sk", "email", "is_current"],
        "dim_org_unit": ["org_unit_name", "org_unit_sk"],
    },
    "headcount": {
        "mart_headcount_monthly": [
            "snapshot_month",
            "active_headcount",
            "resigned_headcount_eom",
            "terminated_headcount_eom",
            "prior_month_active_headcount",
            "net_active_headcount_change_mom",
        ],
        "vw_headcount": ["employee_id", "branch_id", "department_id", "is_active"],
        "mart_employee_current": [
            "emp_no",
            "emp_fullname",
            "location_name",
            "branch_id",
            "employee_sk",
            "legal_entity",
            "emp_status",
            "designation_department",
            "designation",
            "is_on_probation",
            "payroll_group",
        ],
        "dim_designation": ["designation_name", "designation_sk"],
        "fct_lifecycle_event": [
            "employee_sk",
            "event_category",
            "event_name",
            "effective_date",
            "reason",
        ],
        "vw_lifecycle_summary": ["period_label", "event_category", "event_name"],
    },
    "attendance": {
        "vw_attendance_summary": [
            "employee_sk",
            "present_days",
            "scheduled_days",
            "late_count",
            "month",
            "year",
            "overtime_hours",
        ],
        "mart_attendance_monthly_summary": [
            "employee_sk",
            "days_present",
            "days_absent",
            "days_late",
            "year_month",
            "total_overtime_hours",
        ],
        "mart_employee_current": ["emp_fullname", "emp_no", "location_name", "designation_department", "employee_sk"],
        "fct_overtime": ["employee_sk", "total_overtime_hours"],
    },
    "attrition": {
        "vw_turnover": ["department_id", "employee_id", "branch_id"],
        "vw_headcount": ["department_id", "employee_id", "is_active"],
        "fct_lifecycle_event": ["employee_sk", "event_category", "event_name", "effective_date", "reason"],
        "vw_lifecycle_summary": ["effective_date", "event_category", "event_name"],
        "mart_employee_current": ["emp_fullname", "location_name", "join_date", "emp_section_id", "designation_department", "branch_id"],
    },
    "compensation": {
        "vw_salary_bands": ["grade_name", "min_salary", "max_salary", "headcount", "avg_salary"],
        "mart_salary_band_summary": ["grade_name"],
        "mart_employee_current": ["basic_salary", "employee_sk", "location_name", "emp_fullname"],
        "fct_salary_change": ["previous_salary", "new_salary", "effective_date", "employee_sk"],
        "fct_processed_add_ded": ["amount", "employee_sk", "canonical_pay_item_sk"],
        "dim_canonical_pay_item": ["canonical_item_name", "item_type", "canonical_pay_item_sk"],
    },
    "workforce": {
        "mart_employee_current": ["emp_no", "emp_fullname", "branch_name", "employee_id", "shift_id", "source_shift_id"],
        "dim_employee": ["emp_no", "emp_fullname", "shift_id"],
        "dim_shift": ["source_shift_id", "shift_name"],
        "dim_org_unit": ["org_unit_name"],
        "dim_designation": ["designation_name"],
    },
    "performance": {
        "vw_performance_summary": [
            "employee_id",
            "status",
            "rating",
            "period_label",
            "review_year",
        ],
        "mart_employee_current": [
            "designation_department",
            "employee_sk",
            "source_emp_id",
        ],
    },
}


def _mock_qualified_table(short: str) -> str:
    """Semantic views live in hr_semantic; marts/dims in hr (offline eval)."""
    s = str(short).strip()
    if s.lower().startswith("vw_"):
        return f"hr_semantic.{s}"
    return f"hr.{s}"


def mock_grounding_from_expect(
    expect_tables: list[str],
    *,
    eval_domain: str = "",
) -> SchemaGrounding:
    """Synthetic grounding so template / verified matchers can run offline."""
    cols_by_table: dict[str, list[str]] = {}
    domain_cols = _DOMAIN_MOCK_COLUMNS.get(eval_domain.strip().lower(), {})
    for short, cols in domain_cols.items():
        cols_by_table[_mock_qualified_table(short)] = list(cols)
    for raw in expect_tables:
        short = str(raw).rsplit(".", 1)[-1]
        qualified = _mock_qualified_table(short)
        if qualified not in cols_by_table:
            cols_by_table[qualified] = ["_eval"]
    if not cols_by_table:
        cols_by_table["hr.mart_employee_current"] = ["emp_no", "emp_fullname"]
    return SchemaGrounding(columns_by_table=cols_by_table, source="resolve_eval_mock")


def resolve_sql_offline(
    question: str,
    *,
    expect_tables: list[str],
    domain: str,
    template: str | None = None,
    eval_domain: str = "",
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Return ``(tier, sql_source, sql)`` using Tier A/B only.
    """
    grounding = mock_grounding_from_expect(
        expect_tables,
        eval_domain=eval_domain or domain,
    )
    intent = classify_chat_intent(question, last_sql=None, has_prior_post_process=False)
    spec = compile_report_spec(question, chat_intent=intent or ChatIntent.NEW_QUERY)

    if template:
        if spec.template_id != template:
            pass
        routed = try_build_sql_from_report_spec(question, spec, grounding=grounding)
        if routed:
            sql, tag = routed
            return "A", tag, sql

    # Match ``tier_probe``: bank verified SQL before generic Tier-A templates.
    vq = retrieve_verified_sql(
        question,
        grounded_tables={t.rsplit(".", 1)[-1].lower() for t in expect_tables},
        domain=(eval_domain or domain).strip().lower() or None,
        min_score=dm_config.DATAMART_VERIFIED_MIN_SCORE,
    )
    if vq:
        sql, source, _narr = vq
        return "B", source, sql

    if dm_config.DATAMART_PREFER_DETERMINISTIC_SQL:
        report_spec = spec if dm_config.DATAMART_REPORT_SPEC_ENABLED else None
        det = try_resolve_deterministic_sql(
            question,
            grounding=grounding,
            report_spec=report_spec,
        )
        if det:
            sql, source, _narr = det
            return "A", source, sql

    return None, None, None


def eval_resolve_one(case: dict) -> ResolveEvalCaseResult:
    q = str(case["question"]).strip()
    section = str(case.get("section") or "")
    expect = list(case.get("expect_tables") or [])
    template = case.get("template")
    preview = q[:72] + ("…" if len(q) > 72 else "")

    link = eval_one_case(case, check_tier_b=False)
    classified = classify_domain(q).domain.value
    errors: list[str] = []

    eval_domain = str(case.get("eval_domain") or "").strip().lower()
    tier, source, sql = resolve_sql_offline(
        q,
        expect_tables=expect,
        domain=classified,
        template=str(template) if template else None,
        eval_domain=eval_domain,
    )

    if template and not sql:
        errors.append("bank template set but no Tier A SQL resolved")
    elif tier and sql and template and source and not str(source).startswith("verified:"):
        intent = classify_chat_intent(q, last_sql=None, has_prior_post_process=False)
        spec = compile_report_spec(q, chat_intent=intent or ChatIntent.NEW_QUERY)
        if spec.template_id:
            err = validate_sql_against_report_spec(q, sql, spec)
            if err:
                errors.append(f"spec validate: {err}")

    if not link.ok:
        errors.extend(link.errors)

    expect_tier = str(case.get("expect_tier") or "").strip().upper()
    if expect_tier in ("A", "B") and tier != expect_tier:
        errors.append(f"expected tier {expect_tier}, got {tier or 'unresolved'}")

    return ResolveEvalCaseResult(
        section=section,
        question_preview=preview,
        classified_domain=classified,
        tier=tier,
        sql_source=source,
        has_sql=bool(sql),
        link_ok=link.ok,
        errors=errors,
    )


def eval_question_bank_resolve(
    cases: list[dict] | None = None,
    *,
    bank_path=None,
) -> ResolveEvalReport:
    if cases is None:
        _raw, cases = load_question_bank(bank_path)

    results = [eval_resolve_one(c) for c in cases]
    passed = sum(1 for r in results if r.ok)
    tier_a = sum(1 for r in results if r.tier == "A")
    tier_b = sum(1 for r in results if r.tier == "B")
    unresolved = sum(1 for r in results if r.tier is None and not r.errors)
    return ResolveEvalReport(
        total=len(results),
        passed=passed,
        failed=len(results) - passed,
        tier_a=tier_a,
        tier_b=tier_b,
        unresolved=unresolved,
        results=results,
    )
