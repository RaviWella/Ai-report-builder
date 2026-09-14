"""S6: pipeline_meta persistence and question-bank pipeline reporting."""
from app.services.ai_services.datamart.models import (
    DatamartResponse,
    DatamartValidation,
    PipelineTurnMeta,
)
from app.services.ai_services.datamart.pipeline.question_bank_report import (
    pipeline_fields_for_question,
)
from app.services.ai_services.datamart.validation.validation_models import (
    RetrievalValidation,
    ValidationStatus,
)


def test_validation_json_stores_pipeline_meta():
    from app.api.routes.datamart_chat import _validation_to_json

    retrieval = RetrievalValidation(
        status=ValidationStatus.SUFFICIENT,
        tables_selected=["fact_recruitment_pipeline"],
    )
    validation = DatamartValidation(
        retrieval=retrieval,
        overall="verified",
    )
    meta = PipelineTurnMeta(
        domain="recruitment",
        sql_tier="A",
        sql_source="recruitment_pipeline_template",
        tables_linked=["fact_recruitment_pipeline", "dim_candidate"],
    )
    result = DatamartResponse(
        question="recruitment pipeline",
        narrative="ok",
        validation=validation,
        pipeline_meta=meta,
    )
    stored = _validation_to_json(result)
    assert stored is not None
    assert stored["pipeline_meta"]["domain"] == "recruitment"
    assert stored["pipeline_meta"]["sql_tier"] == "A"


def test_question_bank_pipeline_fields_recruitment():
    case = {
        "section": "advanced_recruitment",
        "question": (
            "Prepare a recruitment pipeline report for LinkedIn and referrals "
            "with candidates expected to join in 60 days"
        ),
        "eval_domain": "recruitment",
    }
    fields = pipeline_fields_for_question(
        case,
        sql_source="recruitment_pipeline_template",
        report_spec_domain="workforce",
    )
    assert fields["classified_domain"] == "recruitment"
    assert fields["domain_match"] is True
    assert fields["sql_tier"] == "A"
