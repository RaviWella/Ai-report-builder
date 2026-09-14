"""Backward-compatible alias — use ``sql_resolver.resolve_sql_artifact``."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..validation.pipeline_validation import PipelineValidationState
from ..pipeline_trace import PipelineTracer
from ..orchestration.intent_router import ChatIntent
from ..domain_sql.report_spec import ReportSpec
from ..schema_broker import SchemaGrounding
from .sql_resolver import CATALOG_TEMPLATE_SOURCES, resolve_sql_artifact


@dataclass
class SqlResolution:
    sql: Optional[str]
    narrative: str
    post_process_config: Optional[list]
    sql_source: Optional[str]
    skip_llm: bool
    use_verified_metric: bool
    catalog_sql_source: bool
    llm_output: str
    grounding: SchemaGrounding


def resolve_sql(
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
) -> SqlResolution:
    art = resolve_sql_artifact(
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
    return SqlResolution(
        sql=art.sql,
        narrative=art.narrative,
        post_process_config=art.post_process_config,
        sql_source=art.source,
        skip_llm=art.tier in ("A", "B"),
        use_verified_metric=art.use_verified_metric,
        catalog_sql_source=art.catalog_governed,
        llm_output=art.llm_output,
        grounding=art.grounding or grounding,
    )