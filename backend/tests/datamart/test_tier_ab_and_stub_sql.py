"""Stub SQL detection and Tier A/B probe."""
from app.services.ai_services.datamart.llm.llm_response import (
    is_non_executable_sql,
    is_stub_sql,
    normalize_executable_sql,
)
from app.services.ai_services.datamart.pipeline.tier_probe import try_resolve_tier_ab
from app.services.ai_services.datamart.schema_broker import SchemaGrounding
from app.services.ai_services.datamart.orchestration.intent_router import ChatIntent
from app.services.ai_services.datamart.validation.pipeline_validation import PipelineValidationState


def test_stub_sql_detected():
    assert is_stub_sql("SELECT 1 WHERE FALSE;")
    assert is_stub_sql("select 1 where false")
    assert is_stub_sql("SELECT * FROM t WHERE 1=0")
    assert not is_stub_sql("SELECT emp_no FROM hr.mart_employee_current LIMIT 10")
    assert is_non_executable_sql("SELECT 1 WHERE FALSE")
    assert normalize_executable_sql("SELECT 1 WHERE FALSE") is None


def test_tier_b_probe_recruitment():
    q = (
        "Prepare a recruitment pipeline report showing candidates sourced through LinkedIn "
        "and employee referrals with expected joining date within 60 days."
    )
    grounding = SchemaGrounding(
        columns_by_table={
            "hr.fact_recruitment_pipeline": [
                "candidate_id",
                "recruitment_source",
                "expected_joining_date",
            ],
            "hr.dim_candidate": ["candidate_name", "email"],
            "hr.dim_org_unit": ["org_unit_name"],
        },
        source="test",
    )
    pval = PipelineValidationState(question=q)
    art = try_resolve_tier_ab(
        question=q,
        grounding=grounding,
        chat_intent=ChatIntent.NEW_QUERY,
        report_spec=None,
        is_modify=False,
        is_add_scenario=False,
        targets=[],
        pval=pval,
        domain="recruitment",
    )
    assert art is not None
    assert art.tier in ("A", "B")
    assert art.sql
    assert "fact_recruitment_pipeline" in art.sql.lower()
