"""
Resolve SQL after a fast output-column adequacy check (one regen + pick best).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, Optional

from .. import config as dm_config
from ..pipeline_common import validate_sql_with_grounding
from ..pipeline_retry import RepairBudget, retry_on_error_with_budget
from ..pipeline_trace import PipelineStepStatus, PipelineTracer
from ..domain_sql.report_spec import ReportSpec
from ..domain_sql.report_sql_router import try_build_sql_from_report_spec
from ..schema_broker import SchemaGrounding
from ..sql.sql_answer_adequacy import (
    check_sql_output_columns,
    pick_better_sql_for_question,
)
from ..sql.sql_generation import recover_sql_after_llm

logger = logging.getLogger("ai_services.datamart.adequacy")

REGEN_USER_NOTE = (
    "Report columns did not match your request; regenerated SQL once and kept the best version."
)


@dataclass
class AdequacyResolveResult:
    sql: str
    narrative: str
    post_process_config: Optional[list]
    grounding: SchemaGrounding
    sql_source: Optional[str]
    trace_detail: str
    blocked: bool = False
    block_message: Optional[str] = None
    stored_first_sql: Optional[str] = None
    regen_attempted: bool = False


def _try_catalog_regen(
    question: str,
    *,
    report_spec: Optional[ReportSpec],
    grounding: SchemaGrounding,
) -> Optional[tuple[str, str]]:
    if report_spec and dm_config.DATAMART_REPORT_SPEC_ENABLED:
        routed = try_build_sql_from_report_spec(
            question,
            report_spec,
            grounding=grounding,
        )
        if routed:
            return routed
    recovered = recover_sql_after_llm(
        question=question,
        history_text="",
        narrative="",
        llm_output="",
        llm_sql=None,
        post_process_config=None,
        grounding=grounding,
    )
    if recovered.sql and recovered.source and recovered.source != "llm":
        return recovered.sql, recovered.source
    return None


def _binding_only(
    *,
    sql: str,
    narrative: str,
    post_process_config: Optional[list],
    grounding: SchemaGrounding,
    question: str,
    system_prompt: str,
    retry_fn: Callable,
) -> tuple[str, str, Optional[list], SchemaGrounding, Optional[str]]:
    outcome = validate_sql_with_grounding(
        sql=sql,
        narrative=narrative,
        post_process_config=post_process_config,
        grounding=grounding,
        system_prompt=system_prompt,
        retry_fn=retry_fn,
        allow_retry=False,
        question=question,
        skip_llm_binding_retry=True,
    )
    return (
        outcome.sql,
        outcome.narrative,
        outcome.post_process_config,
        outcome.grounding,
        outcome.error,
    )


def resolve_sql_after_output_check(
    *,
    question: str,
    sql: str,
    narrative: str,
    post_process_config: Optional[list],
    grounding: SchemaGrounding,
    sql_source: Optional[str],
    system_prompt: str,
    retry_fn: Callable,
    repair_budget: RepairBudget,
    trace: PipelineTracer,
    report_spec: Optional[ReportSpec],
    use_verified_sql: bool = False,
    catalog_sql_source: bool = False,
) -> AdequacyResolveResult:
    """
    Fast column adequacy; on failure store SQL, regen once, pick best candidate, execute winner.
    """
    if not dm_config.DATAMART_VALIDATION_REQUIRE_ADEQUACY or use_verified_sql:
        return AdequacyResolveResult(
            sql=sql,
            narrative=narrative,
            post_process_config=post_process_config,
            grounding=grounding,
            sql_source=sql_source,
            trace_detail="Adequacy check skipped",
        )

    err = check_sql_output_columns(question, sql)
    if not err:
        return AdequacyResolveResult(
            sql=sql,
            narrative=narrative,
            post_process_config=post_process_config,
            grounding=grounding,
            sql_source=sql_source,
            trace_detail="Report output columns match",
        )

    first_sql = sql
    first_source = sql_source
    regen_sql: Optional[str] = None
    regen_source: Optional[str] = None
    regen_narrative = narrative
    regen_pp = post_process_config
    regen_grounding = grounding

    if not catalog_sql_source:
        catalog = _try_catalog_regen(
            question,
            report_spec=report_spec,
            grounding=grounding,
        )
        if catalog:
            regen_sql, regen_source = catalog
            regen_sql, regen_narrative, regen_pp, regen_grounding, bind_err = _binding_only(
                sql=regen_sql,
                narrative=narrative,
                post_process_config=post_process_config,
                grounding=grounding,
                question=question,
                system_prompt=system_prompt,
                retry_fn=retry_fn,
            )
            if bind_err:
                regen_sql = None

    if regen_sql is None and repair_budget.can_repair() and not catalog_sql_source:
        logger.warning("Output columns mismatch; one LLM regen: %s", err)
        trace.note_repair("Regenerate SQL for report columns", success=True)
        regen_sql, regen_narrative, regen_pp, fix_error = retry_on_error_with_budget(
            repair_budget,
            trace,
            tag="Regenerate SQL for report columns",
            retry_fn=retry_fn,
            system_prompt=system_prompt,
            sql=sql,
            error=(
                f"Report output columns do not match the question: {err}\n"
                "Rewrite SQL so SELECT lists the attributes the user asked to see. "
                "Use ONLY grounded tables and columns."
            ),
            narrative=narrative,
            post_process_config=post_process_config,
        )
        if fix_error:
            return AdequacyResolveResult(
                sql=first_sql,
                narrative=narrative,
                post_process_config=post_process_config,
                grounding=grounding,
                sql_source=first_source,
                trace_detail=fix_error[:220],
                blocked=True,
                block_message=fix_error,
                stored_first_sql=first_sql,
                regen_attempted=True,
            )
        regen_source = "llm_regen"
        regen_sql, regen_narrative, regen_pp, regen_grounding, bind_err = _binding_only(
            sql=regen_sql,
            narrative=regen_narrative,
            post_process_config=regen_pp,
            grounding=grounding,
            question=question,
            system_prompt=system_prompt,
            retry_fn=retry_fn,
        )
        if bind_err:
            return AdequacyResolveResult(
                sql=first_sql,
                narrative=narrative,
                post_process_config=post_process_config,
                grounding=grounding,
                sql_source=first_source,
                trace_detail=bind_err[:220],
                blocked=True,
                block_message=bind_err,
                stored_first_sql=first_sql,
                regen_attempted=True,
            )

    if regen_sql:
        chosen, tag = pick_better_sql_for_question(question, first_sql, regen_sql)
        final_err = check_sql_output_columns(question, chosen)
        note = REGEN_USER_NOTE
        if tag == "regen_candidate":
            sql_source = regen_source or sql_source
            narrative = regen_narrative
            post_process_config = regen_pp
            grounding = regen_grounding
        if final_err:
            return AdequacyResolveResult(
                sql=chosen or first_sql,
                narrative=(
                    f"{final_err}\n\n"
                    "The query was not executed. Try naming fewer columns or confirm sources."
                ),
                post_process_config=post_process_config,
                grounding=grounding,
                sql_source=sql_source,
                trace_detail=final_err[:220],
                blocked=True,
                block_message="SQL does not answer the question",
                stored_first_sql=first_sql,
                regen_attempted=True,
            )
        detail = f"{note} (kept {tag})"
        trace.note_repair(detail[:160], success=True)
        return AdequacyResolveResult(
            sql=chosen or first_sql,
            narrative=f"{note}\n\n{narrative}".strip() if tag == "regen_candidate" else narrative,
            post_process_config=post_process_config,
            grounding=grounding,
            sql_source=sql_source,
            trace_detail=detail[:220],
            stored_first_sql=first_sql if tag == "regen_candidate" else None,
            regen_attempted=True,
        )

    return AdequacyResolveResult(
        sql=first_sql,
        narrative=(
            f"{err}\n\n"
            "The query was not executed. Try naming fewer columns or confirm sources."
        ),
        post_process_config=post_process_config,
        grounding=grounding,
        sql_source=first_source,
        trace_detail=err[:220],
        blocked=True,
        block_message="SQL does not answer the question",
        stored_first_sql=first_sql,
        regen_attempted=False,
    )
