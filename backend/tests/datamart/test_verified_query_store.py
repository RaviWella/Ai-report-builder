"""Verified query store (Tier B RAG)."""
from __future__ import annotations

from app.services.ai_services.datamart.pipeline.verified_query_store import (
    clear_verified_query_cache,
    retrieve_verified_sql,
)


def test_retrieve_workforce_roster():
    clear_verified_query_cache()
    question = (
        "Generate a workforce report with employee name, company, branch, "
        "department and reporting manager for active employees"
    )
    result = retrieve_verified_sql(
        question,
        grounded_tables={"mart_employee_current", "dim_org_unit"},
        min_score=5,
    )
    assert result is not None
    sql, source, _narr = result
    assert "mart_employee_current" in sql.lower()
    assert source.startswith("verified:")


def test_no_match_without_grounded_tables():
    clear_verified_query_cache()
    question = "Show payroll summary for active employees"
    result = retrieve_verified_sql(
        question,
        grounded_tables={"unrelated_table"},
        min_score=5,
    )
    assert result is None
