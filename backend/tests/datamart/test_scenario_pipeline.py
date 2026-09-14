"""Add-scenario pipeline trace and narrative helpers."""
from app.services.ai_services.datamart.llm.llm_response import extract_narrative
from app.services.ai_services.datamart.pipeline_trace import PipelineStepStatus, PipelineTracer
from app.services.ai_services.datamart.scenario.scenario_pipeline import (
    finish_add_scenario_generate_sql,
    finish_add_scenario_validate_execute,
)


def test_extract_narrative_stops_before_additional_blocks():
    out = """
NARRATIVE:
Here is the leave report summary.

ADDITIONAL_RESULT_BLOCKS:
[{"block_id": "x", "title": "Leave", "sql": "SELECT 1"}]
"""
    assert extract_narrative(out).strip() == "Here is the leave report summary."


def test_add_scenario_trace_completes_generate_sql_step():
    trace = PipelineTracer.begin(repair_attempts_max=1)
    trace.start("generate_sql")
    finish_add_scenario_generate_sql(trace, spec_count=1, llm_had_sql=True)
    built = []
    finish_add_scenario_validate_execute(trace, built=built)
    steps = {s.id: s.status for s in trace.build().steps}
    assert steps["generate_sql"] == PipelineStepStatus.COMPLETED
    assert steps["validate_sql"] in (
        PipelineStepStatus.FAILED,
        PipelineStepStatus.WARNING,
    )
