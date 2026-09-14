"""Add-scenario follow-up: extra result blocks only."""
from __future__ import annotations

from typing import Optional

from ..orchestration.chat_run_context import ChatRunContext
from ..models import DatamartResponse
from ..scenario.scenario_pipeline import (
    attach_block_traces,
    build_add_scenario_message_validation,
    finish_add_scenario_generate_sql,
    finish_add_scenario_no_specs,
    finish_add_scenario_validate_execute,
    recover_add_scenario_specs_with_retry,
)
from ..scenario.extra_blocks import run_extra_datamart_block
from ..validation.validation_runner import validate_extra_result_block
from ..validation.trust_scorer import TrustLevel
from ..schema_broker import SchemaGrounding


def run_add_scenario_turn(
    *,
    question: str,
    narrative: str,
    llm_output: str,
    sql: Optional[str],
    post_process_config: Optional[list],
    system_prompt: str,
    ctx: ChatRunContext,
    grounding: SchemaGrounding,
    history_text: str,
) -> DatamartResponse:
    specs, narrative, llm_output = recover_add_scenario_specs_with_retry(
        question=question,
        narrative=narrative,
        llm_output=llm_output,
        sql=sql,
        post_process_config=post_process_config,
        grounding=grounding,
        history_text=history_text,
        system_prompt=system_prompt,
        repair_budget=ctx.repair_budget,
        trace=ctx.trace,
    )

    if not specs:
        finish_add_scenario_no_specs(
            ctx.trace,
            detail="No valid SQL was produced for the additional scenario.",
        )
        resp = ctx.finish(
            DatamartResponse(
                question=question,
                narrative=narrative or "I could not build SQL for the new scenario.",
                error=None,
            ),
            grounding=grounding,
            binding_passed=False,
            run_critic=False,
        )
        val = build_add_scenario_message_validation(
            ctx.pval, built=[], primary_preserved=True
        )
        return resp.model_copy(update={"validation": val})

    built = []
    for spec in specs:
        blk = run_extra_datamart_block(
            spec=spec,
            system_prompt=system_prompt,
            primary_sql="",
            question=question,
            grounding=grounding,
        )
        block_val = validate_extra_result_block(
            question=question,
            sql=blk.sql,
            grounding=grounding,
            schema_links=ctx.pval.schema_links,
            binding_passed=not blk.error,
            row_count=blk.row_count,
            error=blk.error,
            retrieval=ctx.pval.retrieval,
        )
        if block_val:
            blk = blk.model_copy(update={"validation": block_val})
            try:
                ctx.pval.block_trust_levels.append(TrustLevel(block_val["overall"]))
            except ValueError:
                pass
        built.append(blk)

    finish_add_scenario_generate_sql(
        ctx.trace,
        spec_count=len(specs),
        llm_had_sql=bool(sql and str(sql).strip()),
    )
    finish_add_scenario_validate_execute(ctx.trace, built=built)
    built = attach_block_traces(built, ctx.trace.build())

    if not any(b.columns and b.rows for b in built) and all(b.error for b in built):
        first_err = next((b.error for b in built if b.error), "SQL execution failed")
        resp = ctx.finish(
            DatamartResponse(
                question=question,
                narrative=narrative or first_err,
                sql=None,
                extra_result_blocks=built,
                error=None,
            ),
            grounding=grounding,
            binding_passed=False,
            run_critic=False,
        )
        val = build_add_scenario_message_validation(
            ctx.pval, built=built, primary_preserved=True
        )
        return resp.model_copy(update={"validation": val, "extra_result_blocks": built})

    total_rows = sum(b.row_count for b in built)
    resp = ctx.finish(
        DatamartResponse(
            question=question,
            narrative=narrative,
            sql=None,
            extra_result_blocks=built,
        ),
        grounding=grounding,
        binding_passed=True,
        row_count=total_rows,
        run_critic=False,
    )
    val = build_add_scenario_message_validation(
        ctx.pval, built=built, primary_preserved=True
    )
    return resp.model_copy(update={"validation": val, "extra_result_blocks": built})
