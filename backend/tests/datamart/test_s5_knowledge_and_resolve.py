"""S5: knowledge registry, offline resolve eval, pipeline_meta on responses."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.services.ai_services.datamart.orchestration.chat_run_context import ChatRunContext
from app.services.ai_services.datamart.models import DatamartResponse, PipelineTurnMeta
from app.services.ai_services.datamart.pipeline.domain import DatamartDomain
from app.services.ai_services.datamart.pipeline.knowledge_registry import KnowledgeRegistry
from app.services.ai_services.datamart.pipeline.resolve_eval import (
    resolve_sql_offline,
)
from app.services.ai_services.datamart.pipeline_trace import PipelineStepStatus

BANK_PATH = Path(__file__).resolve().parents[2] / "tools" / "datamart_question_bank.yaml"

RECRUITMENT_QUESTION = (
    "Prepare a recruitment pipeline report showing candidates sourced through LinkedIn "
    "and employee referrals, including candidate name, contact email, recruitment source, "
    "appointment date, expected joining date, and assigned branch. Include only candidates "
    "who are expected to join within the next 60 days."
)


@pytest.fixture(scope="module")
def registry():
    return KnowledgeRegistry.load(bank_path=BANK_PATH)


def test_knowledge_registry_loads_bank_and_verified(registry: KnowledgeRegistry):
    meta = registry.bank_meta()
    assert meta.get("question_count", 0) >= 66
    assert len(registry.bank) >= 66
    assert len(registry.verified) >= 42
    assert "payroll.summary_detail" in registry.template_ids


def test_recruitment_resolves_tier_a_or_b_offline():
    expect = ["fact_recruitment_pipeline", "dim_candidate", "dim_org_unit"]
    tier, source, sql = resolve_sql_offline(
        RECRUITMENT_QUESTION,
        expect_tables=expect,
        domain=DatamartDomain.RECRUITMENT.value,
        eval_domain="recruitment",
    )
    assert tier in ("A", "B"), (tier, source)
    assert sql
    assert source
    if tier == "A":
        assert "recruitment" in source
    else:
        assert source.startswith("verified:")


def test_chat_context_records_pipeline_meta():
    from app.services.ai_services.datamart.validation.validation_models import (
        RetrievalValidation,
        ValidationStatus,
    )

    ctx = ChatRunContext.begin("payroll summary by branch")
    ctx.pval.retrieval = RetrievalValidation(
        status=ValidationStatus.SUFFICIENT,
        tables_selected=["vw_payroll_summary"],
    )
    ctx.record_schema_link(domain="payroll", tables=["vw_payroll_summary"])
    ctx.record_sql_resolve(tier="A", sql_source="payroll_summary_view_template")
    ctx.trace.start("schema_grounding")
    ctx.trace.complete("schema_grounding", PipelineStepStatus.COMPLETED)
    resp = ctx.finish(
        DatamartResponse(question="payroll summary by branch", narrative="ok"),
    )
    assert resp.pipeline_meta is not None
    assert resp.pipeline_meta.domain == "payroll"
    assert resp.pipeline_meta.sql_tier == "A"
    assert resp.pipeline_meta.sql_source == "payroll_summary_view_template"
    assert "vw_payroll_summary" in resp.pipeline_meta.tables_linked


def test_pipeline_eval_ci():
    from tools.run_pipeline_eval import main

    assert main([]) == 0
