"""Add-scenario pipeline: trace, validation, and per-block metadata."""
from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

from ..prompts.chat_prompts import ADD_SCENARIO_RETRY_PROMPT_TEMPLATE
from ..llm.llm_client import LlmRole, call_llm
from ..llm.llm_response import (
    extract_additional_result_blocks,
    extract_narrative,
    is_non_executable_sql,
)
from ..models import DatamartResultBlock, DatamartValidation
from ..pipeline_retry import RepairBudget
from ..pipeline_trace import PipelineStepStatus, PipelineTrace, PipelineTracer
from ..validation.pipeline_validation import PipelineValidationState
from ..llm.prompt_budget import clip_text
from ..schema_broker import SchemaGrounding
from ..sql.sql_binding import validate_sql_bindings
from ..sql.sql_column_allowlist import try_rewrite_unknown_columns
from ..sql.sql_generation import recover_sql_after_llm
from ..validation.validation_models import GenerationValidation, RetrievalValidation, TrustLevel

logger = logging.getLogger("ai_services.datamart.scenario_pipeline")


def finish_add_scenario_generate_sql(
    trace: PipelineTracer,
    *,
    spec_count: int,
    llm_had_sql: bool,
) -> None:
    if spec_count > 0:
        trace.complete(
            "generate_sql",
            PipelineStepStatus.COMPLETED,
            f"SQL for {spec_count} added scenario(s)",
        )
    elif llm_had_sql:
        trace.complete(
            "generate_sql",
            PipelineStepStatus.WARNING,
            "SQL block present but not in ADDITIONAL_RESULT_BLOCKS format",
        )
    else:
        trace.complete(
            "generate_sql",
            PipelineStepStatus.WARNING,
            "No scenario SQL in LLM output (repair/fallback may apply)",
        )


def finish_add_scenario_no_specs(trace: PipelineTracer, *, detail: str) -> None:
    finish_add_scenario_generate_sql(trace, spec_count=0, llm_had_sql=False)
    trace.complete("validate_sql", PipelineStepStatus.FAILED, detail)
    trace.complete(
        "adequacy_check",
        PipelineStepStatus.SKIPPED,
        "No scenario SQL to check",
    )
    trace.complete("execute_query", PipelineStepStatus.FAILED, detail)


def finish_add_scenario_validate_execute(
    trace: PipelineTracer,
    *,
    built: list[DatamartResultBlock],
) -> None:
    trace.start("validate_sql")
    ok_blocks = sum(1 for b in built if b.sql and not b.error)
    warn_blocks = [b for b in built if b.error]
    if not built:
        trace.complete("validate_sql", PipelineStepStatus.FAILED, "No scenarios built")
    elif ok_blocks == len(built):
        trace.complete(
            "validate_sql",
            PipelineStepStatus.COMPLETED,
            f"All {len(built)} scenario(s) passed binding",
        )
    elif ok_blocks:
        trace.complete(
            "validate_sql",
            PipelineStepStatus.WARNING,
            f"{ok_blocks}/{len(built)} scenario(s) OK; others failed validation or execution",
        )
    else:
        trace.complete(
            "validate_sql",
            PipelineStepStatus.FAILED,
            warn_blocks[0].error[:200] if warn_blocks and warn_blocks[0].error else "All scenarios failed",
        )

    trace.complete(
        "adequacy_check",
        PipelineStepStatus.SKIPPED,
        "Checked per added scenario during execution",
    )

    total_rows = sum(b.row_count for b in built)
    trace.complete(
        "execute_query",
        PipelineStepStatus.COMPLETED if ok_blocks else PipelineStepStatus.FAILED,
        f"{total_rows} rows across {len(built)} added scenario(s)"
        if built
        else "No rows returned",
    )


def build_block_pipeline_trace(
    parent: PipelineTrace,
    *,
    block_title: Optional[str],
    block_error: Optional[str],
) -> PipelineTrace:
    """Snapshot of this turn's pathway scoped to one added scenario."""
    label = (block_title or "Added scenario").strip()
    steps = []
    for step in parent.steps:
        detail = step.detail or ""
        if step.id == "generate_sql":
            detail = f"{label}: {detail}" if detail else label
        elif step.id == "execute_query" and block_error:
            detail = block_error[:220]
        steps.append(step.model_copy(update={"detail": detail}))
    return PipelineTrace(
        steps=steps,
        repair_attempts_used=parent.repair_attempts_used,
        repair_attempts_max=parent.repair_attempts_max,
    )


def _spec_sql(spec: dict) -> str:
    return (spec.get("sql") or spec.get("sql_script") or "").strip()


def filter_executable_add_scenario_specs(specs: list[dict]) -> list[dict]:
    """Drop ADDITIONAL_RESULT_BLOCKS entries with NONE / empty / non-SELECT sql."""
    out: list[dict] = []
    for spec in specs:
        if not isinstance(spec, dict):
            continue
        sql = _spec_sql(spec)
        if is_non_executable_sql(sql):
            continue
        out.append(spec)
    return out


def validate_add_scenario_specs_against_grounding(
    specs: list[dict],
    grounding: SchemaGrounding,
) -> tuple[list[dict], Optional[str]]:
    """
    Ensure every scenario SQL stays inside the grounded allowlist.

    Attempts deterministic per-table column rewrite (no LLM) before declaring failure.
    Returns (specs, error_message).
    """
    if not specs:
        return specs, None
    if not grounding.columns_by_table:
        return specs, "No grounded schema was available for validating scenario SQL."

    repaired: list[dict] = []
    for spec in specs:
        sql = _spec_sql(spec)
        err = validate_sql_bindings(sql, grounding)
        if err:
            rewritten = try_rewrite_unknown_columns(sql, grounding)
            if rewritten and rewritten.strip() != sql.strip():
                err2 = validate_sql_bindings(rewritten, grounding)
                if not err2:
                    s2 = dict(spec)
                    s2["sql"] = rewritten
                    repaired.append(s2)
                    continue
            return repaired, err
        repaired.append(spec)
    return repaired, None


def add_scenario_specs_need_retry(
    specs: list[dict],
    *,
    llm_output: str,
) -> tuple[bool, str]:
    """True when we should ask the LLM once more for a valid ADDITIONAL_RESULT_BLOCKS SELECT."""
    if specs:
        return False, ""
    raw = extract_additional_result_blocks(llm_output) or []
    if raw:
        return (
            True,
            "ADDITIONAL_RESULT_BLOCKS was present but every entry had sql set to NONE, empty, "
            "or a non-SELECT. You must output one object with a valid PostgreSQL SELECT.",
        )
    return (
        True,
        "No executable SELECT was produced for the added scenario. Output NARRATIVE plus "
        "ADDITIONAL_RESULT_BLOCKS (one JSON array, one object) with a valid sql field — never NONE.",
    )


def retry_add_scenario_llm(
    *,
    system_prompt: str,
    question: str,
    schema_context: str,
    narrative: str,
    llm_output: str,
    error_detail: str,
) -> str:
    """One repair LLM call to regenerate ADDITIONAL_RESULT_BLOCKS with executable SQL."""
    prior = clip_text(llm_output or "", 2_400, "prior_llm_output")
    schema = clip_text(schema_context or "", 4_000, "schema")
    retry_prompt = ADD_SCENARIO_RETRY_PROMPT_TEMPLATE.format(
        error=error_detail,
        question=question.strip(),
        schema_context=schema,
        narrative=(narrative or "").strip()[:800],
        prior_output=prior,
    )
    logger.info("Add-scenario: retrying LLM for ADDITIONAL_RESULT_BLOCKS")
    return call_llm(system_prompt, retry_prompt, role=LlmRole.REPAIR)


def recover_add_scenario_specs(
    *,
    question: str,
    narrative: str,
    llm_output: str,
    sql: Optional[str],
    post_process_config: Optional[list],
    grounding: SchemaGrounding,
    history_text: str,
) -> list[dict]:
    """Parse ADDITIONAL_RESULT_BLOCKS or recover standalone SQL for one new scenario."""
    raw_blocks = extract_additional_result_blocks(llm_output) or []
    specs = list(raw_blocks)
    if sql and str(sql).strip() and not specs:
        specs = [
            {
                "block_id": str(uuid.uuid4()),
                "title": (question[:80] or "New scenario").strip(),
                "sql": sql,
                "post_process": post_process_config,
            }
        ]
    specs = filter_executable_add_scenario_specs(specs)
    if specs:
        return specs
    # Blocks were present but NONE/empty — do not substitute catalog primary SQL.
    if raw_blocks:
        return []

    outcome = recover_sql_after_llm(
        question=question,
        history_text=history_text,
        narrative=narrative,
        llm_output=llm_output,
        llm_sql=None,
        post_process_config=post_process_config,
        grounding=grounding,
    )
    if outcome.sql and not is_non_executable_sql(outcome.sql):
        return [
            {
                "block_id": str(uuid.uuid4()),
                "title": (question[:80] or "New scenario").strip(),
                "sql": outcome.sql,
                "post_process": outcome.post_process_config,
            }
        ]
    return []


def recover_add_scenario_specs_with_retry(
    *,
    question: str,
    narrative: str,
    llm_output: str,
    sql: Optional[str],
    post_process_config: Optional[list],
    grounding: SchemaGrounding,
    history_text: str,
    system_prompt: str,
    repair_budget: RepairBudget,
    trace: Optional[PipelineTracer] = None,
) -> tuple[list[dict], str, str]:
    """
    Parse scenario specs; on NONE / missing SQL, consume one repair attempt and re-ask the LLM.

    Returns ``(specs, narrative, llm_output_used)``.
    """
    llm_used = llm_output
    narrative_out = narrative
    specs = recover_add_scenario_specs(
        question=question,
        narrative=narrative,
        llm_output=llm_output,
        sql=sql,
        post_process_config=post_process_config,
        grounding=grounding,
        history_text=history_text,
    )
    specs, bind_err = validate_add_scenario_specs_against_grounding(specs, grounding)
    if bind_err:
        need_retry, reason = True, f"Schema binding error for added scenario SQL: {bind_err}"
    else:
        need_retry, reason = add_scenario_specs_need_retry(specs, llm_output=llm_output)
    if not need_retry or not repair_budget.consume():
        return specs, narrative_out, llm_used

    if trace is not None:
        trace.start("sql_repair", "Retry add-scenario ADDITIONAL_RESULT_BLOCKS")

    try:
        retry_output = retry_add_scenario_llm(
            system_prompt=system_prompt,
            question=question,
            schema_context=grounding.to_prompt_text(),
            narrative=narrative,
            llm_output=llm_output,
            error_detail=reason,
        )
        llm_used = retry_output
        narrative_out = extract_narrative(retry_output) or narrative_out
        specs = recover_add_scenario_specs(
            question=question,
            narrative=narrative_out,
            llm_output=retry_output,
            sql=None,
            post_process_config=post_process_config,
            grounding=grounding,
            history_text=history_text,
        )
        specs, _err2 = validate_add_scenario_specs_against_grounding(specs, grounding)
        if trace is not None:
            trace.note_repair(
                "Add-scenario blocks retry"
                + (f" ({len(specs)} spec(s))" if specs else " — still no valid SQL"),
                success=bool(specs),
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Add-scenario LLM retry failed: %s", exc)
        if trace is not None:
            trace.note_repair(f"Add-scenario retry failed: {exc}", success=False)

    return specs, narrative_out, llm_used


def build_add_scenario_message_validation(
    pval: PipelineValidationState,
    *,
    built: list[DatamartResultBlock],
    primary_preserved: bool,
) -> DatamartValidation:
    """
    Message-level validation for an add-scenario turn — scoped to the scenario(s)
    added in this turn only (not the preserved primary).
    """
    if built:
        for blk in reversed(built):
            if not blk.validation or not isinstance(blk.validation, dict):
                continue
            v = blk.validation
            try:
                overall = TrustLevel(str(v.get("overall", "needs_review")))
            except ValueError:
                overall = TrustLevel.NEEDS_REVIEW
            ret_raw = v.get("retrieval")
            retrieval = (
                RetrievalValidation.model_validate(ret_raw)
                if isinstance(ret_raw, dict)
                else (pval.retrieval or RetrievalValidation(status="sufficient", tables_selected=[]))
            )
            gen_raw = v.get("generation")
            generation = (
                GenerationValidation.model_validate(gen_raw)
                if isinstance(gen_raw, dict)
                else None
            )
            return DatamartValidation(
                retrieval=retrieval,
                generation=generation,
                overall=overall,
            )

    retrieval = pval.retrieval or RetrievalValidation(
        status="sufficient",
        tables_selected=[],
    )
    generation = GenerationValidation(
        binding="skipped",
        warnings=["No SQL was produced for the added scenario."],
    )
    overall = (
        TrustLevel.NEEDS_REVIEW
        if primary_preserved
        else TrustLevel.BLOCKED
    )
    return DatamartValidation(
        retrieval=retrieval,
        generation=generation,
        overall=overall,
    )


def attach_block_traces(
    built: list[DatamartResultBlock],
    parent_trace: PipelineTrace,
) -> list[DatamartResultBlock]:
    out: list[DatamartResultBlock] = []
    for blk in built:
        out.append(
            blk.model_copy(
                update={
                    "pipeline_trace": build_block_pipeline_trace(
                        parent_trace,
                        block_title=blk.title,
                        block_error=blk.error,
                    )
                }
            )
        )
    return out
