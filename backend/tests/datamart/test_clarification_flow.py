"""Clarification reply merge and validation flags."""
from app.services.ai_services.datamart.orchestration.clarification_flow import (
    merge_clarified_question,
    validation_awaiting_clarification,
)
from app.services.ai_services.datamart.validation.pipeline_validation import PipelineValidationState
from app.services.ai_services.datamart.schema_broker import SchemaGrounding
from app.services.ai_services.datamart.validation.validation_context import enrich_retrieval_with_grounding
from app.services.ai_services.datamart.validation.validation_models import (
    RetrievalValidation,
    ValidationStatus,
)
from app.services.ai_services.datamart.models import DatamartResponse


def test_merge_clarified_question_combines_anchor_and_reply():
    merged = merge_clarified_question(
        "List employees with bank details",
        "All active staff in the Singapore entity",
    )
    assert "List employees with bank details" in merged
    assert "Singapore entity" in merged
    assert "Additional clarification" in merged


def test_validation_awaiting_clarification_flag():
    assert validation_awaiting_clarification({"awaiting_clarification": True})
    assert not validation_awaiting_clarification({"overall": "verified"})


def test_enrich_retrieval_adds_columns_in_context():
    grounding = SchemaGrounding(
        columns_by_table={
            "hr.mart_employee_current": ["emp_no", "emp_fullname", "employee_sk"],
            "hr.dim_bank": ["bank_name", "source_bank_id"],
        },
        source="test",
    )
    retrieval = RetrievalValidation(status=ValidationStatus.SUFFICIENT)
    enriched = enrich_retrieval_with_grounding(retrieval, grounding)
    assert "mart_employee_current" in enriched.columns_in_context
    assert "emp_no" in enriched.columns_in_context["mart_employee_current"]


def test_finish_marks_awaiting_clarification_when_ui_enabled(monkeypatch):
    from app.services.ai_services.datamart import config as dm_config
    from app.services.ai_services.datamart.orchestration.chat_run_context import ChatRunContext

    monkeypatch.setattr(dm_config, "DATAMART_CHAT_CLARIFICATION_UI", True)
    ctx = ChatRunContext.begin("How many employees?")
    ctx.pval.retrieval = RetrievalValidation(status=ValidationStatus.AMBIGUOUS)
    grounding = SchemaGrounding(
        columns_by_table={"hr.mart_employee_current": ["emp_no"]},
        source="test",
    )
    out = ctx.finish_clarification(
        DatamartResponse(question="How many employees?", narrative="Please clarify."),
        grounding=grounding,
    )
    assert out.validation is not None
    assert out.validation.awaiting_clarification is True
    assert out.validation.anchor_question == "How many employees?"
    assert out.validation.retrieval.columns_in_context.get("mart_employee_current")
