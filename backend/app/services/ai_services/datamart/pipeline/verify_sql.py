"""
S2 unified SQL verification: link tables → binding → syntax → output columns.

Replaces separate validate_sql / adequacy_check steps in the user-visible pathway.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, Optional

from .. import config as dm_config
from ..validation.adequacy_resolve import resolve_sql_after_output_check
from ..postprocess.is_current_policy import apply_is_current_policy
from ..orchestration.modify_mode import check_modify_sql_anchored
from ..pipeline_common import validate_sql_with_grounding
from ..pipeline_trace import PipelineStepStatus, PipelineTracer
from ..pipeline_retry import RepairBudget
from ..orchestration.refinement_guard import check_refinement_preserves_sql
from ..domain_sql.report_spec import ReportSpec
from ..schema_broker import SchemaGrounding
from ..sql.sql_fast_path import rewrite_hallucinated_table_names
from ..sql.sql_null_policy import apply_null_row_policy
from ..llm.llm_response import validate_sql_syntax
from ..orchestration.intent_router import ChatIntent
from .artifacts import VerifyResult
from .sql_table_guard import assert_sql_tables_in_link

logger = logging.getLogger("ai_services.datamart.verify_sql")


@dataclass(frozen=True, slots=True)
class VerifyInput:
    question: str
    sql: str
    narrative: str
    post_process_config: Optional[list]
    grounding: SchemaGrounding
    system_prompt: str
    catalog_governed: bool
    use_verified_metric: bool
    sql_source: Optional[str]
    report_spec: Optional[ReportSpec]
    chat_intent: ChatIntent
    anchor_sql: Optional[str]
    broker_last_sql: Optional[str]
    is_modify: bool


def verify_sql(
    inp: VerifyInput,
    *,
    trace: PipelineTracer,
    repair_budget: RepairBudget,
    retry_fn: Callable,
) -> VerifyResult:
    """
    Run all pre-execute checks. On success, ``passed`` is True and ``blocked`` is False.
    """
    errors: list[str] = []
    sql = inp.sql
    narrative = inp.narrative
    post_process_config = inp.post_process_config
    grounding = inp.grounding

    trace.start("validate_sql")

    link_err = assert_sql_tables_in_link(sql, grounding)
    if link_err:
        errors.append(link_err)
        trace.complete("validate_sql", PipelineStepStatus.FAILED, link_err[:220])
        return VerifyResult(
            passed=False,
            sql=sql,
            narrative=narrative,
            post_process_config=post_process_config,
            grounding=grounding,
            detail=link_err,
            errors=errors,
            blocked=True,
        )

    sql = rewrite_hallucinated_table_names(sql, grounding)

    if inp.is_modify and inp.anchor_sql:
        anchor_err = check_modify_sql_anchored(anchor_sql=inp.anchor_sql, new_sql=sql)
        if anchor_err:
            trace.complete("validate_sql", PipelineStepStatus.BLOCKED, anchor_err[:220])
            return VerifyResult(
                passed=False,
                sql=sql,
                narrative=narrative,
                post_process_config=post_process_config,
                grounding=grounding,
                detail=anchor_err,
                errors=[anchor_err],
                blocked=True,
            )

    if dm_config.DATAMART_REPORT_SPEC_ENABLED and inp.broker_last_sql:
        refine_err = check_refinement_preserves_sql(
            question=inp.question,
            prior_sql=inp.broker_last_sql,
            new_sql=sql,
            chat_intent=inp.chat_intent,
        )
        if refine_err:
            trace.complete("validate_sql", PipelineStepStatus.BLOCKED, refine_err[:220])
            return VerifyResult(
                passed=False,
                sql=sql,
                narrative=narrative,
                post_process_config=post_process_config,
                grounding=grounding,
                detail=refine_err,
                errors=[refine_err],
                blocked=True,
            )

    allow_binding_retry = repair_budget.can_repair() and not inp.catalog_governed
    outcome = validate_sql_with_grounding(
        sql=sql,
        narrative=narrative,
        post_process_config=post_process_config,
        grounding=grounding,
        system_prompt=inp.system_prompt,
        retry_fn=retry_fn,
        allow_retry=allow_binding_retry,
        question=inp.question,
        skip_llm_binding_retry=inp.catalog_governed,
    )
    if outcome.error:
        trace.complete("validate_sql", PipelineStepStatus.FAILED, outcome.error[:220])
        return VerifyResult(
            passed=False,
            sql=sql,
            narrative=narrative,
            post_process_config=post_process_config,
            grounding=grounding,
            detail=outcome.error,
            errors=[outcome.error],
            blocked=True,
        )

    sql = outcome.sql
    narrative = outcome.narrative
    post_process_config = outcome.post_process_config
    grounding = outcome.grounding

    sql, _ = apply_is_current_policy(sql, question=inp.question, grounding=grounding)
    sql, _ = apply_null_row_policy(sql, question=inp.question)

    syntax_err = validate_sql_syntax(sql)
    if syntax_err:
        errors.append(f"Syntax: {syntax_err}")
        trace.complete("validate_sql", PipelineStepStatus.FAILED, syntax_err[:220])
        return VerifyResult(
            passed=False,
            sql=sql,
            narrative=narrative,
            post_process_config=post_process_config,
            grounding=grounding,
            detail=syntax_err,
            errors=errors,
            blocked=True,
        )

    # Output column adequacy (folded into validate_sql trace)
    skip_adequacy = inp.catalog_governed and dm_config.DATAMART_FAST_PATH_LIGHT_VALIDATION
    adequacy_detail = "Binding and syntax OK"
    if not skip_adequacy and dm_config.DATAMART_VALIDATION_REQUIRE_ADEQUACY:
        trace.start("adequacy_check")
        adequacy = resolve_sql_after_output_check(
            question=inp.question,
            sql=sql,
            narrative=narrative,
            post_process_config=post_process_config,
            grounding=grounding,
            sql_source=inp.sql_source,
            system_prompt=inp.system_prompt,
            retry_fn=retry_fn,
            repair_budget=repair_budget,
            trace=trace,
            report_spec=inp.report_spec if dm_config.DATAMART_REPORT_SPEC_ENABLED else None,
            use_verified_sql=inp.use_verified_metric,
            catalog_sql_source=inp.catalog_governed,
        )
        sql = adequacy.sql
        narrative = adequacy.narrative
        post_process_config = adequacy.post_process_config
        grounding = adequacy.grounding
        adequacy_detail = adequacy.trace_detail[:220]
        if adequacy.blocked:
            trace.complete("adequacy_check", PipelineStepStatus.BLOCKED, adequacy_detail)
            trace.complete("validate_sql", PipelineStepStatus.BLOCKED, adequacy_detail)
            return VerifyResult(
                passed=False,
                sql=sql,
                narrative=narrative,
                post_process_config=post_process_config,
                grounding=grounding,
                detail=adequacy.block_message or adequacy_detail,
                errors=[adequacy.block_message or "Column adequacy failed"],
                blocked=True,
            )
        trace.complete("adequacy_check", PipelineStepStatus.COMPLETED, adequacy_detail)
    else:
        trace.start("adequacy_check")
        trace.complete(
            "adequacy_check",
            PipelineStepStatus.SKIPPED,
            "Governed SQL" if skip_adequacy else "Adequacy disabled",
        )

    detail = f"{adequacy_detail}"
    trace.complete("validate_sql", PipelineStepStatus.COMPLETED, detail[:220])
    return VerifyResult(
        passed=True,
        sql=sql,
        narrative=narrative,
        post_process_config=post_process_config,
        grounding=grounding,
        detail=detail,
        errors=[],
        blocked=False,
    )
