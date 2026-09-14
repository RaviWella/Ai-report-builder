"""Tier B verified SQL must not match across domains (regression for screenshot bug)."""
from app.services.ai_services.datamart.pipeline.verified_query_store import (
    clear_verified_query_cache,
    retrieve_verified_sql,
)


def test_leave_verified_not_used_for_recruitment_domain():
    clear_verified_query_cache()
    recruitment_grounded = {
        "fact_recruitment_pipeline",
        "dim_candidate",
        "dim_org_unit",
        "vw_payroll_summary",
        "mart_headcount_monthly",
    }
    payrollish_question = (
        "Show payroll summary by branch with basic salary for active employees"
    )
    # High token overlap with leave/payroll verified entries — domain must block
    assert (
        retrieve_verified_sql(
            payrollish_question,
            grounded_tables=recruitment_grounded,
            domain="recruitment",
            min_score=5,
        )
        is None
    )
