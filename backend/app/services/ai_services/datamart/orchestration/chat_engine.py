"""
Datamart SQL turn engine — resolve SQL (S2) and verify (unified gate).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from .intent_router import ChatIntent
from ..pipeline.artifacts import SqlArtifact, VerifyResult
from ..pipeline.sql_resolver import resolve_sql_artifact
from ..pipeline.verify_sql import VerifyInput, verify_sql
from ..pipeline_trace import PipelineTracer
from ..validation.pipeline_validation import PipelineValidationState
from ..pipeline_retry import RepairBudget
from ..domain_sql.report_spec import ReportSpec
from ..schema_broker import SchemaGrounding
from ..pipeline.sql_resolver import CATALOG_TEMPLATE_SOURCES

__all__ = ["CATALOG_TEMPLATE_SOURCES", "SqlTurnResult", "generate_sql_for_turn", "validate_sql_for_turn"]


@dataclass
class SqlTurnResult:
    sql: Optional[str]
    narrative: str
    post_process_config: Optional[list]
    sql_source: Optional[str]
    skip_llm_for_sql: bool
    use_verified_sql: bool
    catalog_sql_source: bool
    llm_output: str
    grounding: SchemaGrounding
    tier: str = "C"
    needs_clarification: bool = False
    clarification_message: str = ""


def generate_sql_for_turn(
    *,
    question: str,
    history_text: str,
    grounding: SchemaGrounding,
    system_prompt: str,
    user_prompt: str,
    trace: PipelineTracer,
    chat_intent: ChatIntent,
    report_spec: Optional[ReportSpec],
    is_modify: bool,
    is_add_scenario: bool,
    targets: list[str],
    pval: PipelineValidationState,
    domain: str | None = None,
) -> SqlTurnResult:
    artifact: SqlArtifact = resolve_sql_artifact(
        question=question,
        history_text=history_text,
        grounding=grounding,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        trace=trace,
        chat_intent=chat_intent,
        report_spec=report_spec,
        is_modify=is_modify,
        is_add_scenario=is_add_scenario,
        targets=targets,
        pval=pval,
        domain=domain,
    )
    g = artifact.grounding or grounding
    skip_llm = artifact.tier in ("A", "B")
    return SqlTurnResult(
        sql=artifact.sql,
        narrative=artifact.narrative,
        post_process_config=artifact.post_process_config,
        sql_source=artifact.source,
        skip_llm_for_sql=skip_llm,
        use_verified_sql=artifact.use_verified_metric,
        catalog_sql_source=artifact.catalog_governed,
        llm_output=artifact.llm_output,
        grounding=g,
        tier=artifact.tier,
        needs_clarification=artifact.needs_clarification,
        clarification_message=artifact.clarification_message,
    )


def validate_sql_for_turn(
    *,
    sql: str,
    narrative: str,
    post_process_config: Optional[list],
    grounding: SchemaGrounding,
    system_prompt: str,
    question: str,
    trace: PipelineTracer,
    catalog_sql_source: bool,
    allow_retry: bool,
    retry_fn: Callable,
    repair_budget: RepairBudget,
    use_verified_sql: bool = False,
    sql_source: Optional[str] = None,
    report_spec: Optional[ReportSpec] = None,
    chat_intent: ChatIntent = ChatIntent.NEW_QUERY,
    anchor_sql: Optional[str] = None,
    broker_last_sql: Optional[str] = None,
    is_modify: bool = False,
) -> tuple[str, str, Optional[list], SchemaGrounding, Optional[str]]:
    """Unified S2 verification; returns bind_err message when blocked."""
    _ = allow_retry  # retry budget handled inside verify_sql via repair_budget
    result: VerifyResult = verify_sql(
        VerifyInput(
            question=question,
            sql=sql,
            narrative=narrative,
            post_process_config=post_process_config,
            grounding=grounding,
            system_prompt=system_prompt,
            catalog_governed=catalog_sql_source,
            use_verified_metric=use_verified_sql,
            sql_source=sql_source,
            report_spec=report_spec,
            chat_intent=chat_intent,
            anchor_sql=anchor_sql,
            broker_last_sql=broker_last_sql,
            is_modify=is_modify,
        ),
        trace=trace,
        repair_budget=repair_budget,
        retry_fn=retry_fn,
    )
    if result.blocked or not result.passed:
        return (
            result.sql,
            result.narrative,
            result.post_process_config,
            result.grounding,
            result.detail,
        )
    return (
        result.sql,
        result.narrative,
        result.post_process_config,
        result.grounding,
        None,
    )
