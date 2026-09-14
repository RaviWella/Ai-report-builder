"""Pipeline trace and repair budget."""
from app.services.ai_services.datamart.orchestration.chat_run_context import ChatRunContext
from app.services.ai_services.datamart.models import DatamartResponse
from app.services.ai_services.datamart.pipeline_retry import RepairBudget
from app.services.ai_services.datamart.pipeline_trace import (
    PipelineStepStatus,
    PipelineTracer,
)


def test_tracer_records_steps_and_skips_unused_repair():
    tracer = PipelineTracer.begin(repair_attempts_max=1)
    tracer.start("schema_grounding", "3 tables")
    tracer.complete("schema_grounding", PipelineStepStatus.COMPLETED, "3 tables")
    tracer.start("retrieval_check")
    tracer.complete("retrieval_check", PipelineStepStatus.WARNING, "ambiguous")
    trace = tracer.build()
    ids = [s.id for s in trace.steps]
    assert "schema_grounding" in ids
    assert "retrieval_check" in ids
    assert "sql_repair" not in ids


def test_tracer_includes_repair_when_used():
    tracer = PipelineTracer.begin(repair_attempts_max=1)
    tracer.note_repair("binding fix", success=True)
    trace = tracer.build()
    assert any(s.id == "sql_repair" for s in trace.steps)
    assert trace.repair_attempts_used == 1


def test_chat_run_context_finish_attaches_trace():
    from app.services.ai_services.datamart.validation.validation_models import (
        RetrievalValidation,
        ValidationStatus,
    )

    ctx = ChatRunContext.begin("headcount by department")
    ctx.pval.retrieval = RetrievalValidation(
        status=ValidationStatus.SUFFICIENT,
        tables_selected=["employees"],
    )
    ctx.trace.start("schema_grounding")
    ctx.trace.complete("schema_grounding", PipelineStepStatus.COMPLETED)
    resp = ctx.finish(
        DatamartResponse(question="headcount by department", narrative="ok"),
    )
    assert resp.pipeline_trace is not None
    assert len(resp.pipeline_trace.steps) >= 1


def test_repair_budget_allows_at_most_max_attempts():
    budget = RepairBudget(max_attempts=1)
    assert budget.consume() is True
    assert budget.used == 1
    assert budget.consume() is False
    assert budget.can_repair() is False
