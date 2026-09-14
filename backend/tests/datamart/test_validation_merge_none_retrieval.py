"""Validation attachment when retrieval state was never populated."""
from app.services.ai_services.datamart.models import DatamartResponse
from app.services.ai_services.datamart.validation.validation_runner import merge_validation


def test_merge_validation_accepts_none_retrieval():
    validation = merge_validation(None)
    assert validation is not None
    assert validation.retrieval is not None
    assert validation.retrieval.status.value == "sufficient"


def test_finish_validated_response_with_empty_pval():
    from app.services.ai_services.datamart.validation.pipeline_validation import (
        PipelineValidationState,
        finish_validated_response,
    )

    pval = PipelineValidationState(question="add bank details")
    resp = finish_validated_response(
        pval,
        DatamartResponse(question="add bank details", narrative="ok", sql="SELECT 1"),
        sql="SELECT 1",
        run_critic=False,
    )
    assert resp.validation is not None
