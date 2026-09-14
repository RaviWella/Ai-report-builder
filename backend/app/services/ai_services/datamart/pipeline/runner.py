"""
Simplified datamart chat with bounded SQL recovery loop and UI-visible events.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

from ..llm.llm_client import call_llm
from ..llm.llm_response import extract_narrative, extract_sql, is_non_executable_sql
from ..models import DatamartResponse, FollowUpMode, PipelineTurnMeta
from ..pipeline_trace import PipelineStepStatus, PipelineTracer
from ..schema import execute_sql
from ..prompts.simple_context import (
    SimpleChatContext,
    build_simple_chat_context,
    expand_simple_chat_context,
)
from ..prompts.simple_history import SimpleTurnContext, prepare_simple_turn_context
from ..prompts.simple_prompts import (
    SIMPLE_SQL_SYSTEM,
    SqlAttemptRecord,
    build_simple_retry_prompt,
    build_simple_user_prompt,
)
from ..sql.sql_exec_guard import ensure_select_limit
from ..orchestration.modify_mode import check_modify_sql_anchored
from ..sql.sql_exec_repairs import try_repair_sql_execution_error, try_repair_zero_row_sql
from ..sql.sql_recovery import (
    MAX_SQL_ATTEMPTS,
    RecoveryActionKind,
    diagnose_sql_failure,
    diagnose_zero_row_filters,
    plan_recovery,
    tables_for_recovery,
)
from ..semantic.column_value_peek import analyze_zero_row_filters

logger = logging.getLogger("ai_services.datamart.runner")


def _attach_trace(resp: DatamartResponse, trace: PipelineTracer) -> DatamartResponse:
    built = trace.build()
    narrative = resp.narrative
    if built.recovery_events and not resp.error:
        n = len(built.recovery_events)
        narrative = (
            f"{narrative}\n\n(Recovered after {n} adjustment"
            f"{'' if n == 1 else 's'} — see “How this answer was built”.)"
        ).strip()
    return resp.model_copy(
        update={
            "narrative": narrative,
            "pipeline_trace": built,
            "pipeline_meta": PipelineTurnMeta(
                domain="simple",
                sql_tier="C",
                sql_source="llm",
                tables_linked=[],
            ),
        }
    )


def _generate_sql(
    *,
    question: str,
    turn: SimpleTurnContext,
    ctx: SimpleChatContext,
    retry: Optional[tuple[str, str]] = None,
    attempt: int = 1,
    prior_attempts: list[SqlAttemptRecord] | None = None,
    llm_guidance: str = "",
    tables_added_this_retry: list[str] | None = None,
) -> tuple[str, Optional[str], str]:
    if retry:
        failed_sql, err = retry
        user_prompt = build_simple_retry_prompt(
            question=question,
            failed_sql=failed_sql,
            error_message=err,
            mappings_text=ctx.mappings_text,
            datahub_text=ctx.datahub_text,
            schema_text=ctx.schema_text,
            mode_instructions=turn.mode_instructions,
            history_text=turn.history_for_prompt,
            attempt=attempt,
            max_attempts=MAX_SQL_ATTEMPTS,
            prior_attempts=prior_attempts,
            llm_guidance=llm_guidance,
            tables_added_this_retry=tables_added_this_retry,
        )
    else:
        user_prompt = build_simple_user_prompt(
            question=question,
            history_text=turn.history_for_prompt,
            mappings_text=ctx.mappings_text,
            datahub_text=ctx.datahub_text,
            schema_text=ctx.schema_text,
            mode_instructions=turn.mode_instructions,
        )
    llm_out = call_llm(SIMPLE_SQL_SYSTEM, user_prompt)
    sql = extract_sql(llm_out)
    narrative = extract_narrative(llm_out) or "Here are the results for your question."
    return llm_out, sql, narrative


def _log_recovery(
    trace: PipelineTracer,
    *,
    attempt: int,
    phase: str,
    plan,
) -> None:
    trace.note_recovery(
        attempt=attempt,
        phase=phase,
        issue=plan.issue.kind.value,
        action=plan.action.value,
        detail=plan.detail,
        user_message=plan.user_message,
    )


def run_chat_pipeline(
    question: str,
    history_text: str,
    previous_post_process_config: Optional[list[dict]] = None,
    follow_up_mode: Optional[FollowUpMode] = None,
    target_scenario_ids: Optional[list[str]] = None,
    previous_extra_result_blocks: Optional[list[dict]] = None,
    previous_primary_sql: Optional[str] = None,
    confirmed_table_names: Optional[list[str]] = None,
) -> DatamartResponse:
    del confirmed_table_names

    trace = PipelineTracer.begin(repair_attempts_max=MAX_SQL_ATTEMPTS)
    q = (question or "").strip()
    if not q:
        trace.complete("schema_grounding", PipelineStepStatus.FAILED, "Empty question")
        return _attach_trace(
            DatamartResponse(question=question, narrative="Please enter a question."),
            trace,
        )

    turn = prepare_simple_turn_context(
        question=q,
        history_text=history_text,
        follow_up_mode=follow_up_mode,
        previous_primary_sql=previous_primary_sql,
        previous_post_process_config=previous_post_process_config,
        previous_extra_result_blocks=previous_extra_result_blocks,
        target_scenario_ids=target_scenario_ids,
    )

    trace.start("schema_grounding")
    t0 = time.perf_counter()
    try:
        ctx = build_simple_chat_context(q)
    except Exception as exc:  # noqa: BLE001
        logger.exception("simple context build failed")
        trace.complete("schema_grounding", PipelineStepStatus.FAILED, str(exc)[:200])
        trace.skip_remaining("schema_grounding", reason="Context load failed")
        return _attach_trace(
            DatamartResponse(
                question=q,
                narrative="Could not load warehouse schema context.",
                error=str(exc)[:500],
            ),
            trace,
        )

    ms = int((time.perf_counter() - t0) * 1000)
    tables_preview = ", ".join(ctx.grounding.qualified_tables[:8])
    suffix = ""
    if len(ctx.grounding.qualified_tables) > 8:
        suffix = f" (+{len(ctx.grounding.qualified_tables) - 8} more)"
    mode_tag = (
        "modify" if turn.is_modify else "scenario" if turn.is_add_scenario else "new"
    )
    trace.complete(
        "schema_grounding",
        PipelineStepStatus.COMPLETED,
        f"{len(ctx.grounding.qualified_tables)} tables: {tables_preview}{suffix} ({ms}ms) · mode={mode_tag}",
    )

    if not ctx.grounding.columns_by_table:
        trace.skip_remaining("schema_grounding", reason="No warehouse columns")
        return _attach_trace(
            DatamartResponse(
                question=q,
                narrative=(
                    "I could not load any warehouse tables. "
                    "Check the database connection and DATAMART_QUERY_SCHEMAS."
                ),
            ),
            trace,
        )

    sql: Optional[str] = None
    narrative = ""
    last_error = ""
    retry_pair: Optional[tuple[str, str]] = None
    prior_attempts: list[SqlAttemptRecord] = []
    pending_guidance = ""
    pending_tables_added: list[str] = []
    gen_ms = 0

    for attempt in range(1, MAX_SQL_ATTEMPTS + 1):
        if attempt > 1 and last_error:
            issue = diagnose_sql_failure(sql, last_error)
            plan = plan_recovery(issue, attempt=attempt - 1, max_attempts=MAX_SQL_ATTEMPTS)
            if plan.action == RecoveryActionKind.ABORT:
                break
            pending_guidance = issue.llm_guidance
            pending_tables_added = []
            if plan.action == RecoveryActionKind.EXPAND_CONTEXT:
                _log_recovery(trace, attempt=attempt, phase="context", plan=plan)
                trace.start(
                    "schema_grounding",
                    plan.user_message[:200],
                )
                before_tables = set(ctx.table_short_names)
                extra = tables_for_recovery(issue, sql)
                ctx = expand_simple_chat_context(ctx, q, extra_tables=extra)
                pending_tables_added = [
                    t for t in ctx.table_short_names if t not in before_tables
                ]
                trace.complete(
                    "schema_grounding",
                    PipelineStepStatus.COMPLETED,
                    f"Expanded to {len(ctx.grounding.qualified_tables)} tables",
                )

        trace.start(
            "generate_sql",
            f"Attempt {attempt}/{MAX_SQL_ATTEMPTS}"
            if attempt > 1
            else None,
        )
        t1 = time.perf_counter()
        try:
            _, sql, narrative = _generate_sql(
                question=q,
                turn=turn,
                ctx=ctx,
                retry=retry_pair,
                attempt=attempt,
                prior_attempts=prior_attempts,
                llm_guidance=pending_guidance,
                tables_added_this_retry=pending_tables_added or None,
            )
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
            issue = diagnose_sql_failure(sql, last_error)
            plan = plan_recovery(issue, attempt=attempt, max_attempts=MAX_SQL_ATTEMPTS)
            _log_recovery(trace, attempt=attempt, phase="generate", plan=plan)
            trace.complete("generate_sql", PipelineStepStatus.WARNING, last_error[:180])
            prior_attempts.append(
                SqlAttemptRecord(
                    attempt=attempt,
                    failed_sql=sql or "",
                    error=last_error,
                    issue_kind=issue.kind.value,
                    user_hint=issue.user_hint,
                    llm_guidance=issue.llm_guidance,
                    action_taken=plan.action.value,
                    tables_added=tuple(pending_tables_added),
                )
            )
            retry_pair = (sql or "", last_error)
            pending_guidance = ""
            pending_tables_added = []
            if plan.action == RecoveryActionKind.ABORT:
                break
            continue

        gen_ms = int((time.perf_counter() - t1) * 1000)

        if is_non_executable_sql(sql):
            last_error = "No SQL in LLM response"
            issue = diagnose_sql_failure(None, last_error)
            plan = plan_recovery(issue, attempt=attempt, max_attempts=MAX_SQL_ATTEMPTS)
            _log_recovery(trace, attempt=attempt, phase="generate", plan=plan)
            trace.complete("generate_sql", PipelineStepStatus.WARNING, last_error)
            prior_attempts.append(
                SqlAttemptRecord(
                    attempt=attempt,
                    failed_sql="",
                    error=last_error,
                    issue_kind=issue.kind.value,
                    user_hint=issue.user_hint,
                    llm_guidance=issue.llm_guidance,
                    action_taken=plan.action.value,
                    tables_added=tuple(pending_tables_added),
                )
            )
            retry_pair = ("", last_error)
            pending_guidance = issue.llm_guidance
            pending_tables_added = []
            if plan.action == RecoveryActionKind.ABORT:
                break
            continue

        if turn.is_modify and turn.anchor_sql and sql:
            anchor_err = check_modify_sql_anchored(
                anchor_sql=turn.anchor_sql,
                new_sql=sql,
            )
            if anchor_err:
                last_error = anchor_err
                issue = diagnose_sql_failure(sql, last_error)
                plan = plan_recovery(
                    issue,
                    attempt=attempt,
                    max_attempts=MAX_SQL_ATTEMPTS,
                )
                _log_recovery(trace, attempt=attempt, phase="generate", plan=plan)
                trace.complete(
                    "generate_sql",
                    PipelineStepStatus.WARNING,
                    last_error[:180],
                )
                prior_attempts.append(
                    SqlAttemptRecord(
                        attempt=attempt,
                        failed_sql=sql,
                        error=last_error,
                        issue_kind="modify_not_anchored",
                        user_hint="Modify must edit the anchored SQL in place.",
                        llm_guidance=(
                            "Edit the anchored SQL below — same FROM/JOIN/WHERE base — "
                            "and apply only the user's requested change."
                        ),
                        action_taken=plan.action.value,
                        tables_added=tuple(pending_tables_added),
                    )
                )
                retry_pair = (sql, last_error)
                pending_guidance = (
                    "Edit the anchored SQL in place; do not switch to unrelated tables."
                )
                pending_tables_added = []
                if plan.action == RecoveryActionKind.ABORT:
                    break
                continue

        trace.complete(
            "generate_sql",
            PipelineStepStatus.COMPLETED,
            f"SQL ready ({gen_ms}ms) · attempt {attempt}/{MAX_SQL_ATTEMPTS}",
        )

        trace.start("execute_query")
        sql_run = ensure_select_limit(sql or "")
        t2 = time.perf_counter()

        def _finish_ok(
            final_sql: str,
            cols: list[str],
            rws: list[list],
            count: int,
        ) -> DatamartResponse:
            exec_ms = int((time.perf_counter() - t2) * 1000)
            trace.complete(
                "execute_query",
                PipelineStepStatus.COMPLETED,
                f"{count} rows ({exec_ms}ms)",
            )
            return _attach_trace(
                DatamartResponse(
                    question=q,
                    narrative=narrative,
                    sql=final_sql,
                    columns=cols,
                    rows=rws,
                    row_count=count,
                ),
                trace,
            )

        try:
            columns, rows, row_count = execute_sql(sql_run, validate_binding=False)
            if row_count == 0 and attempt < MAX_SQL_ATTEMPTS:
                zero_analysis = analyze_zero_row_filters(
                    sql_run, ctx.grounding.columns_by_table
                )
                if zero_analysis and zero_analysis.has_actionable_mismatch:
                    last_error = zero_analysis.to_error_message()
                    issue = diagnose_zero_row_filters(
                        sql_run,
                        error_message=last_error,
                        llm_guidance=zero_analysis.llm_guidance(),
                    )
                    zero_plan = plan_recovery(
                        issue,
                        attempt=attempt,
                        max_attempts=MAX_SQL_ATTEMPTS,
                        repair_available=True,
                    )
                    if zero_plan.action == RecoveryActionKind.REPAIR_SQL:
                        _log_recovery(
                            trace, attempt=attempt, phase="execute", plan=zero_plan
                        )
                        repaired = try_repair_zero_row_sql(sql_run, zero_analysis)
                        if repaired and repaired.strip() != sql_run.strip():
                            try:
                                columns, rows, row_count = execute_sql(
                                    repaired, validate_binding=False
                                )
                                if row_count > 0:
                                    trace.note_recovery(
                                        attempt=attempt,
                                        phase="execute",
                                        issue=issue.kind.value,
                                        action="repair_sql_success",
                                        detail="filter_literal_repair",
                                        user_message="Fixed WHERE filter values and ran successfully.",
                                    )
                                    return _finish_ok(repaired, columns, rows, row_count)
                                sql_run = repaired
                            except Exception as repair_exc:  # noqa: BLE001
                                last_error = str(repair_exc)
                    _log_recovery(trace, attempt=attempt, phase="execute", plan=zero_plan)
                    trace.complete(
                        "execute_query",
                        PipelineStepStatus.WARNING,
                        last_error[:200],
                    )
                    prior_attempts.append(
                        SqlAttemptRecord(
                            attempt=attempt,
                            failed_sql=sql_run,
                            error=last_error,
                            issue_kind=issue.kind.value,
                            user_hint=issue.user_hint,
                            llm_guidance=issue.llm_guidance,
                            action_taken=zero_plan.action.value,
                            tables_added=tuple(pending_tables_added),
                        )
                    )
                    retry_pair = (sql_run, last_error)
                    pending_guidance = issue.llm_guidance
                    pending_tables_added = []
                    if zero_plan.action == RecoveryActionKind.ABORT:
                        break
                    continue
            return _finish_ok(sql_run, columns, rows, row_count)
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
            issue = diagnose_sql_failure(sql_run, last_error)
            repair_plan = plan_recovery(
                issue,
                attempt=attempt,
                max_attempts=MAX_SQL_ATTEMPTS,
                repair_available=issue.repairable,
            )
            if repair_plan.action == RecoveryActionKind.REPAIR_SQL:
                _log_recovery(trace, attempt=attempt, phase="execute", plan=repair_plan)
                repaired = try_repair_sql_execution_error(
                    sql_run, last_error, ctx.grounding
                )
                if repaired and repaired.strip() != sql_run.strip():
                    try:
                        columns, rows, row_count = execute_sql(
                            repaired, validate_binding=False
                        )
                        trace.note_recovery(
                            attempt=attempt,
                            phase="execute",
                            issue=issue.kind.value,
                            action="repair_sql_success",
                            detail="deterministic_join_repair",
                            user_message="Fixed join keys and ran successfully.",
                        )
                        return _finish_ok(repaired, columns, rows, row_count)
                    except Exception as repair_exc:  # noqa: BLE001
                        last_error = str(repair_exc)

            _log_recovery(trace, attempt=attempt, phase="execute", plan=repair_plan)
            exec_ms = int((time.perf_counter() - t2) * 1000)
            trace.complete(
                "execute_query",
                PipelineStepStatus.WARNING
                if attempt < MAX_SQL_ATTEMPTS
                else PipelineStepStatus.FAILED,
                last_error[:200] + (f" ({exec_ms}ms)" if exec_ms else ""),
            )
            prior_attempts.append(
                SqlAttemptRecord(
                    attempt=attempt,
                    failed_sql=sql_run,
                    error=last_error,
                    issue_kind=issue.kind.value,
                    user_hint=issue.user_hint,
                    llm_guidance=issue.llm_guidance,
                    action_taken=repair_plan.action.value,
                    tables_added=tuple(pending_tables_added),
                )
            )
            retry_pair = (sql_run, last_error)
            pending_guidance = issue.llm_guidance
            pending_tables_added = []
            if repair_plan.action == RecoveryActionKind.ABORT:
                break

    trace.complete("generate_sql", PipelineStepStatus.FAILED, "Could not produce working SQL")
    fail_msg = (
        f"I could not run a working query after {MAX_SQL_ATTEMPTS} attempts. "
        f"Last error: {(last_error or 'unknown')[:300]}"
    )
    return _attach_trace(
        DatamartResponse(
            question=q,
            narrative=narrative or fail_msg,
            sql=sql if sql and not is_non_executable_sql(sql) else None,
            error=last_error[:2000] if last_error else None,
        ),
        trace,
    )
