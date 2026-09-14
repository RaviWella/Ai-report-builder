"""Retrieval validation and schema linker tests."""
from app.services.ai_services.datamart.orchestration.intent_router import ChatIntent
from app.services.ai_services.datamart.validation.retrieval_validator import validate_retrieval
from app.services.ai_services.datamart.schema_broker import SchemaGrounding
from app.services.ai_services.datamart.orchestration.schema_linker import build_schema_links
from app.services.ai_services.datamart.semantic.semantic_layer import clear_catalog_cache, resolve_semantics
from app.services.ai_services.datamart.validation.validation_models import ValidationStatus


def setup_function() -> None:
    clear_catalog_cache()


def _grounding(*tables: str) -> SchemaGrounding:
    cols = {f"hr_semantic.{t}": ["employee_id", "full_name"] for t in tables}
    return SchemaGrounding(columns_by_table=cols, source="test")


def test_payroll_core_tables_not_listed_missing_when_in_grounding():
    q = "Show top 10 employees by basic salary from payroll"
    semantics = resolve_semantics(q)
    grounding = _grounding("dim_employee", "fact_payroll_detail")
    links = build_schema_links(q, semantics, grounding)
    result = validate_retrieval(
        question=q,
        grounding=grounding,
        semantics=semantics,
        schema_links=links,
        chat_intent=ChatIntent.NEW_QUERY,
    )
    assert "dim_employee" in result.tables_selected
    assert "fact_payroll_detail" not in result.missing_tables
    assert "dim_employee" not in result.missing_tables


def test_insufficient_when_required_seed_table_missing():
    q = "Show top 10 employees by basic salary from payroll"
    semantics = resolve_semantics(q)
    grounding = _grounding("dim_employee")
    links = build_schema_links(q, semantics, grounding)
    result = validate_retrieval(
        question=q,
        grounding=grounding,
        semantics=semantics,
        schema_links=links,
        chat_intent=ChatIntent.NEW_QUERY,
    )
    if semantics.metrics_matched or "payroll" in semantics.topics_matched:
        assert result.status == ValidationStatus.INSUFFICIENT or result.missing_tables
