"""S1 schema link: domain classification and domain-scoped pruning."""
from __future__ import annotations

from app.services.ai_services.datamart.pipeline.domain import DatamartDomain
from app.services.ai_services.datamart.pipeline.domain_classifier import classify_domain
from app.services.ai_services.datamart.pipeline.schema_link_stage import (
    _catalog_must_include_tables,
    _prune_to_domain_allowlist,
)
from app.services.ai_services.datamart.semantic.semantic_layer import resolve_semantics
from app.services.ai_services.datamart.pipeline.verified_query_store import (
    clear_verified_query_cache,
    retrieve_verified_sql,
)
from app.services.ai_services.datamart.schema_broker import SchemaGrounding

RECRUITMENT_QUESTION = (
    "Prepare a recruitment pipeline report showing candidates sourced through LinkedIn "
    "and employee referrals, including candidate name, contact email, recruitment source, "
    "appointment date, expected joining date, and assigned branch. Include only candidates "
    "who are expected to join within the next 60 days"
)


def test_classify_recruitment_over_payroll_keywords():
    result = classify_domain(RECRUITMENT_QUESTION)
    assert result.domain == DatamartDomain.RECRUITMENT
    assert result.scores.get("recruitment", 0) > result.scores.get("payroll", 0)


def test_catalog_must_include_recruitment_and_bindings():
    semantics = resolve_semantics(RECRUITMENT_QUESTION)
    tables = _catalog_must_include_tables(
        RECRUITMENT_QUESTION,
        domain=DatamartDomain.RECRUITMENT,
        semantics=semantics,
        report_spec=None,
        confirmed=None,
    )
    lowered = {t.lower() for t in tables}
    assert "fact_recruitment_pipeline" in lowered
    assert "dim_candidate" in lowered
    assert "dim_org_unit" in lowered


def test_prune_keeps_protected_catalog_tables():
    semantics = resolve_semantics(RECRUITMENT_QUESTION)
    protected = frozenset(
        t.lower()
        for t in _catalog_must_include_tables(
            RECRUITMENT_QUESTION,
            domain=DatamartDomain.RECRUITMENT,
            semantics=semantics,
            report_spec=None,
            confirmed=None,
        )
    )
    grounding = SchemaGrounding(
        columns_by_table={
            "hr.vw_payroll_summary": ["basic_salary"],
            "hr.mart_headcount_monthly": ["employee_count"],
            "hr.fact_recruitment_pipeline": ["candidate_id", "recruitment_source"],
            "hr.dim_candidate": ["candidate_name", "email"],
            "hr.dim_org_unit": ["org_unit_name"],
            "hr.mart_employee_current": ["emp_fullname", "location_name"],
            "hr.dim_employee": ["employee_id"],
            "hr.fact_leave_balance": ["employee_id"],
            "hr.vw_leave_summary": ["leave_days"],
            "hr.dim_job": ["job_title"],
        },
        source="test",
    )
    pruned = _prune_to_domain_allowlist(
        grounding,
        DatamartDomain.RECRUITMENT,
        max_tables=5,
        protected_short_names=protected,
    )
    shorts = {t.lower() for t in pruned.table_short_names}
    assert "fact_recruitment_pipeline" in shorts
    assert "dim_candidate" in shorts


def test_prune_drops_payroll_tables_for_recruitment_domain():
    grounding = SchemaGrounding(
        columns_by_table={
            "hr.vw_payroll_summary": ["basic_salary"],
            "hr.mart_headcount_monthly": ["employee_count"],
            "hr.fact_recruitment_pipeline": ["candidate_id", "recruitment_source"],
            "hr.dim_candidate": ["candidate_name", "email"],
            "hr.dim_org_unit": ["org_unit_name"],
        },
        source="test",
    )
    pruned = _prune_to_domain_allowlist(
        grounding,
        DatamartDomain.RECRUITMENT,
        max_tables=8,
    )
    shorts = {t.lower() for t in pruned.table_short_names}
    assert "fact_recruitment_pipeline" in shorts
    assert "dim_candidate" in shorts
    assert "vw_payroll_summary" not in shorts
    assert "mart_headcount_monthly" not in shorts


def test_tier_b_rejects_leave_sql_for_recruitment_domain():
    clear_verified_query_cache()
    leave_question = (
        "Generate a report of employees and leave details for approved leave only"
    )
    grounded = {
        "fact_leave_balance",
        "mart_employee_current",
        "fact_recruitment_pipeline",
        "dim_candidate",
    }
    assert (
        retrieve_verified_sql(
            leave_question,
            grounded_tables=grounded,
            domain="recruitment",
        )
        is None
    )
    match = retrieve_verified_sql(
        RECRUITMENT_QUESTION,
        grounded_tables=grounded,
        domain="recruitment",
        min_score=5,
    )
    assert match is not None
    sql, source, _ = match
    assert source.startswith("verified:recruitment")
    assert "fact_recruitment_pipeline" in sql.lower()
