"""Pipeline validation state attaches retrieval + generation on all exits."""
from app.services.ai_services.datamart.orchestration.intent_router import ChatIntent
from app.services.ai_services.datamart.models import DatamartResponse
from app.services.ai_services.datamart.validation.pipeline_validation import PipelineValidationState
from app.services.ai_services.datamart.schema_broker import SchemaGrounding
from app.services.ai_services.datamart.validation.validation_models import (
    GenerationValidation,
    RetrievalValidation,
    ValidationStatus,
)


def _grounding() -> SchemaGrounding:
    return SchemaGrounding(
        columns_by_table={"hr_semantic.dim_employee": ["employee_id", "full_name"]},
        source="test",
    )


def test_finish_attaches_retrieval_and_generation():
    retrieval = RetrievalValidation(
        status=ValidationStatus.SUFFICIENT,
        tables_selected=["dim_employee"],
    )
    pval = PipelineValidationState(
        question="count employees",
        retrieval=retrieval,
        schema_links=[],
    )
    resp = pval.finish(
        DatamartResponse(question="count employees", narrative="ok", sql="SELECT 1"),
        sql="SELECT COUNT(*) FROM hr_semantic.dim_employee",
        grounding=_grounding(),
        binding_passed=True,
        row_count=1,
    )
    assert resp.validation is not None
    assert resp.validation.retrieval.status == ValidationStatus.SUFFICIENT
    assert resp.validation.generation is not None


def test_finish_with_prebuilt_generation():
    retrieval = RetrievalValidation(status=ValidationStatus.AMBIGUOUS)
    gen = GenerationValidation(binding="failed", warnings=["bad join"])
    pval = PipelineValidationState(question="q", retrieval=retrieval)
    resp = pval.finish(
        DatamartResponse(question="q", error="bind"),
        sql="SELECT 1",
        grounding=_grounding(),
        binding_passed=False,
        generation=gen,
    )
    assert resp.validation is not None
    assert resp.validation.generation.binding == "failed"
