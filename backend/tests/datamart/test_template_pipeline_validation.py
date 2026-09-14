"""Template pipeline attaches validation on error and success paths."""
from unittest.mock import patch

from app.services.ai_services.datamart import config as dm_config
from app.services.ai_services.datamart.schema_broker import SchemaGrounding
from app.services.ai_services.datamart.orchestration.template_pipeline import run_template_modification_pipeline
from app.services.ai_services.datamart.validation.validation_models import ValidationStatus


def _grounding() -> SchemaGrounding:
    return SchemaGrounding(
        columns_by_table={"public_mint_audit.dim_employee": ["employee_id", "full_name"]},
        source="test",
    )


@patch("app.services.ai_services.datamart.orchestration.template_pipeline.build_schema_grounding")
@patch("app.services.ai_services.datamart.orchestration.template_pipeline.call_llm")
def test_template_binding_error_includes_validation(mock_llm, mock_ground, monkeypatch):
    monkeypatch.setattr(dm_config, "DATAMART_VALIDATION_ENABLED", True)
    mock_ground.return_value = _grounding()
    mock_llm.return_value = "NARRATIVE: ok\nSQL:\nSELECT bad_col FROM public_mint_audit.dim_employee\n"

    with patch(
        "app.services.ai_services.datamart.orchestration.template_pipeline.validate_sql_with_grounding"
    ) as mock_validate:
        from app.services.ai_services.datamart.pipeline_common import SqlValidationOutcome

        mock_validate.return_value = SqlValidationOutcome(
            sql="SELECT bad_col FROM public_mint_audit.dim_employee",
            narrative="ok",
            post_process_config=None,
            grounding=_grounding(),
            error="Column 'bad_col' not in allowlist",
        )
        resp = run_template_modification_pipeline(
            question="add column",
            history_text="",
            template_sql="SELECT employee_id FROM public_mint_audit.dim_employee",
            template_narrative="",
            template_post_process_config=None,
        )

    assert resp.error
    assert resp.validation is not None
    assert resp.validation.retrieval.status == ValidationStatus.SUFFICIENT


@patch("app.services.ai_services.datamart.orchestration.template_pipeline.build_schema_grounding")
@patch("app.services.ai_services.datamart.orchestration.template_pipeline.call_llm")
@patch("app.services.ai_services.datamart.orchestration.template_pipeline.validate_sql_with_grounding")
def test_template_success_includes_validation(mock_validate, mock_llm, mock_ground, monkeypatch):
    monkeypatch.setattr(dm_config, "DATAMART_VALIDATION_ENABLED", True)
    mock_ground.return_value = _grounding()
    mock_llm.return_value = (
        "NARRATIVE: ok\nSQL:\nSELECT employee_id FROM public_mint_audit.dim_employee\n"
    )
    from app.services.ai_services.datamart.pipeline_common import SqlValidationOutcome

    mock_validate.return_value = SqlValidationOutcome(
        sql="SELECT employee_id FROM public_mint_audit.dim_employee",
        narrative="ok",
        post_process_config=None,
        grounding=_grounding(),
    )

    with patch("app.services.ai_services.datamart.orchestration.template_pipeline.apply_is_current_policy") as mock_pol:
        mock_pol.return_value = ("SELECT employee_id FROM public_mint_audit.dim_employee", False)
        resp = run_template_modification_pipeline(
            question="limit 5",
            history_text="",
            template_sql="SELECT employee_id FROM public_mint_audit.dim_employee",
            template_narrative="",
            template_post_process_config=None,
        )

    assert resp.validation is not None
    assert resp.validation.generation is not None
