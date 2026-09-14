"""Retrieval relevance post-filter on grounded tables."""
from app.services.ai_services.datamart.validation.retrieval_relevance import apply_retrieval_relevance_filter
from app.services.ai_services.datamart.schema_broker import SchemaGrounding
from app.services.ai_services.datamart.semantic.semantic_layer import clear_catalog_cache, resolve_semantics


def setup_function() -> None:
    clear_catalog_cache()


def test_filters_unrelated_tables():
    q = "Show top 10 employees by basic salary from payroll"
    semantics = resolve_semantics(q)
    cols = {
        "hr_semantic.dim_employee": ["employee_id", "basic_salary"],
        "hr_semantic.fact_payroll_detail": ["employee_id", "basic_salary"],
        "hr_semantic.dim_date": ["date_key"],
    }
    grounding = SchemaGrounding(columns_by_table=cols, source="test")
    filtered = apply_retrieval_relevance_filter(
        question=q,
        grounding=grounding,
        semantics=semantics,
        max_tables=2,
    )
    shorts = filtered.table_short_names
    assert "dim_date" not in shorts
    assert "dim_employee" in shorts
