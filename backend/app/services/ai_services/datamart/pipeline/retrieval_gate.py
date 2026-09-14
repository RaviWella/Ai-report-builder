"""Legacy retrieval validation overlay (after S1 schema link)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .. import config as dm_config
from ..orchestration.clarification_messages import build_retrieval_clarification_message
from ..orchestration.intent_router import ChatIntent
from ..models import DatamartResponse
from ..workspace.observability import log_retrieval_validation
from ..pipeline_trace import PipelineStepStatus, PipelineTracer
from ..validation.pipeline_validation import PipelineValidationState
from ..domain_sql.report_spec import ReportSpec, spec_required_tables
from ..validation.report_spec_validate import validate_retrieval_for_spec
from ..schema_broker import SchemaGrounding, ensure_grounding_includes_tables
from ..sql.sql_fast_path import try_resolve_deterministic_sql
from ..validation.validation_runner import run_retrieval_validation
from .turn_setup import ChatTurnSetup


@dataclass
class RetrievalGateResult:
    grounding: SchemaGrounding
    pval: PipelineValidationState
    blocked_response: Optional[DatamartResponse] = None


def run_retrieval_gate(
    setup: ChatTurnSetup,
    *,
    grounding: SchemaGrounding,
    ctx_trace: PipelineTracer,
    finish_clarification,
) -> RetrievalGateResult:
    """Run retrieval_check step; may return a clarification response to stop the turn."""
    pval = PipelineValidationState(
        question=setup.question,
        report_spec=setup.report_spec,
    )
    if not dm_config.DATAMART_VALIDATION_ENABLED:
        ctx_trace.complete("retrieval_check", PipelineStepStatus.SKIPPED, "Validation disabled")
        return RetrievalGateResult(grounding=grounding, pval=pval)

    retrieval_val, schema_links = run_retrieval_validation(
        question=setup.question,
        grounding=grounding,
        chat_intent=setup.chat_intent,
    )
    pval = PipelineValidationState(
        question=setup.question,
        retrieval=retrieval_val,
        schema_links=schema_links,
        report_spec=setup.report_spec,
    )
    log_retrieval_validation(
        pipeline="chat",
        status=retrieval_val.status.value,
        overall_tables=retrieval_val.tables_selected,
    )
    r_status = retrieval_val.status.value
    block_insufficient = (
        dm_config.DATAMART_VALIDATION_ENFORCE_RETRIEVAL
        or dm_config.DATAMART_VALIDATION_BLOCK_INSUFFICIENT_EXEC
    )

    if r_status == "insufficient" and retrieval_val.missing_tables:
        repaired = ensure_grounding_includes_tables(
            grounding, retrieval_val.missing_tables
        )
        if len(repaired.table_short_names) > len(grounding.table_short_names):
            grounding = repaired
            retrieval_val, schema_links = run_retrieval_validation(
                question=setup.question,
                grounding=grounding,
                chat_intent=setup.chat_intent,
            )
            pval.retrieval = retrieval_val
            pval.schema_links = schema_links
            r_status = retrieval_val.status.value
            log_retrieval_validation(
                pipeline="chat",
                status=retrieval_val.status.value,
                overall_tables=retrieval_val.tables_selected,
            )

    if setup.report_spec:
        spec_err = validate_retrieval_for_spec(
            setup.report_spec, grounding.table_short_names
        )
        if spec_err:
            repaired = ensure_grounding_includes_tables(
                grounding, list(spec_required_tables(setup.report_spec))
            )
            if len(repaired.table_short_names) > len(grounding.table_short_names):
                grounding = repaired
                spec_err = validate_retrieval_for_spec(
                    setup.report_spec, grounding.table_short_names
                )
            if spec_err and block_insufficient:
                ctx_trace.complete(
                    "retrieval_check", PipelineStepStatus.BLOCKED, spec_err[:220]
                )
                ctx_trace.skip_remaining(
                    "retrieval_check", reason="Stopped — report spec tables missing"
                )
                return RetrievalGateResult(
                    grounding=grounding,
                    pval=pval,
                    blocked_response=finish_clarification(
                        DatamartResponse(
                            question=setup.question,
                            narrative=build_retrieval_clarification_message(
                                question=setup.question,
                                retrieval=retrieval_val,
                            ),
                            error=None,
                        ),
                        grounding=grounding,
                    ),
                )

    if r_status == "insufficient":
        ctx_trace.complete(
            "retrieval_check",
            PipelineStepStatus.BLOCKED,
            retrieval_val.message or "Insufficient schema context",
        )
    elif r_status == "ambiguous":
        ctx_trace.complete(
            "retrieval_check",
            PipelineStepStatus.WARNING,
            retrieval_val.message or "Ambiguous context",
        )
    else:
        note = (
            "Context sufficient (repaired)"
            if grounding.source.endswith("+required")
            else "Context sufficient"
        )
        ctx_trace.complete(
            "retrieval_check",
            PipelineStepStatus.COMPLETED,
            retrieval_val.message or note,
        )

    fast_path_ready = _fast_path_available(setup, grounding)
    if block_insufficient and r_status == "insufficient" and not fast_path_ready:
        ctx_trace.skip_remaining(
            "retrieval_check", reason="Stopped — fix retrieval before generating SQL"
        )
        return RetrievalGateResult(
            grounding=grounding,
            pval=pval,
            blocked_response=finish_clarification(
                DatamartResponse(
                    question=setup.question,
                    narrative=build_retrieval_clarification_message(
                        question=setup.question,
                        retrieval=retrieval_val,
                    ),
                    error=None,
                ),
                grounding=grounding,
            ),
        )
    if (
        dm_config.DATAMART_CHAT_CLARIFY_ON_AMBIGUOUS
        and r_status == "ambiguous"
        and retrieval_val
        and not fast_path_ready
    ):
        ctx_trace.skip_remaining(
            "retrieval_check", reason="Stopped — clarify ambiguous question before SQL"
        )
        return RetrievalGateResult(
            grounding=grounding,
            pval=pval,
            blocked_response=finish_clarification(
                DatamartResponse(
                    question=setup.question,
                    narrative=build_retrieval_clarification_message(
                        question=setup.question,
                        retrieval=retrieval_val,
                    ),
                    error=None,
                ),
                grounding=grounding,
            ),
        )

    return RetrievalGateResult(grounding=grounding, pval=pval)


def _fast_path_available(setup: ChatTurnSetup, grounding: SchemaGrounding) -> bool:
    if not (
        dm_config.DATAMART_PREFER_DETERMINISTIC_SQL
        and dm_config.DATAMART_FAST_PATH_SKIP_AMBIGUOUS_BLOCK
        and setup.chat_intent == ChatIntent.NEW_QUERY
        and not setup.is_modify
        and not setup.is_add_scenario
    ):
        return False
    return (
        try_resolve_deterministic_sql(
            setup.question,
            grounding=grounding,
            report_spec=setup.report_spec
            if dm_config.DATAMART_REPORT_SPEC_ENABLED
            else None,
        )
        is not None
    )
