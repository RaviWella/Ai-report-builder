"""Warehouse execution and post-processing for a chat turn."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Callable, Optional

from ..config import MAX_SQL_RETRIES
from ..llm.llm_response import is_non_executable_sql, merge_post_process_configs
from ..models import DatamartResponse
from ..postprocess.narrative_insights import enrich_narrative_from_results
from ..pipeline_trace import PipelineStepStatus, PipelineTracer
from ..pipeline_retry import retry_on_error_with_budget
from ..postprocess.post_process_validate import validate_post_process_config
from ..postprocess.post_processor import (
    apply as apply_post_processing,
    finalize_datamart_rows_after_post_process,
    shrink_outer_limit_for_append_sql,
)
from ..schema import execute_sql
from ..schema_broker import SchemaGrounding
from ..sql.sql_exec_guard import ensure_select_limit, is_warehouse_timeout_error
from ..sql.sql_exec_repairs import try_repair_sql_execution_error
from ..orchestration.chat_run_context import ChatRunContext
from ..orchestration.intent_router import ChatIntent

logger = logging.getLogger("ai_services.datamart.execute_stage")


@dataclass
class ExecuteResult:
    sql: str
    narrative: str
    post_process_config: Optional[list]
    columns: list[str]
    rows: list[list]
    row_count: int
    raw_columns: Optional[list[str]]
    raw_rows: Optional[list[list]]
    raw_row_count: Optional[int]
    exec_ms: int
    blocked_response: Optional[DatamartResponse] = None
    partial_response: Optional[DatamartResponse] = None


def execute_sql_turn(
    *,
    ctx: ChatRunContext,
    question: str,
    sql: str,
    narrative: str,
    post_process_config: Optional[list],
    grounding: SchemaGrounding,
    prior_pp: Optional[list],
    system_prompt: str,
    chat_intent: ChatIntent,
    retry_fn: Callable,
    build_clarification,
) -> ExecuteResult:
    if is_non_executable_sql(sql):
        ctx.trace.complete("execute_query", PipelineStepStatus.BLOCKED, "No executable SQL")
        return ExecuteResult(
            sql=sql,
            narrative=narrative,
            post_process_config=post_process_config,
            columns=[],
            rows=[],
            row_count=0,
            raw_columns=None,
            raw_rows=None,
            raw_row_count=None,
            exec_ms=0,
            blocked_response=build_clarification("non_executable_sql"),
        )

    ctx.trace.start("execute_query")
    columns: list[str] = []
    rows: list[list] = []
    row_count = 0
    last_error: Optional[str] = None
    t0 = time.perf_counter()

    for attempt in range(MAX_SQL_RETRIES + 1):
        try:
            sql_run = ensure_select_limit(
                shrink_outer_limit_for_append_sql(sql, post_process_config)
            )
            columns, rows, row_count = execute_sql(sql_run, grounding)
            last_error = None
            break
        except RuntimeError as exc:
            last_error = str(exc)
            logger.warning(
                "SQL execution failed (attempt %d/%d): %s",
                attempt + 1,
                MAX_SQL_RETRIES + 1,
                last_error,
            )
            if is_warehouse_timeout_error(last_error):
                break
            repaired = try_repair_sql_execution_error(sql, last_error, grounding)
            if repaired:
                sql = repaired
                continue
            if attempt < MAX_SQL_RETRIES and ctx.repair_budget.can_repair():
                sql, narrative, post_process_config, fix_error = retry_on_error_with_budget(
                    ctx.repair_budget,
                    ctx.trace,
                    tag="Fix warehouse execution error",
                    retry_fn=retry_fn,
                    system_prompt=system_prompt,
                    sql=sql,
                    error=last_error,
                    narrative=narrative,
                    post_process_config=post_process_config,
                )
                if fix_error:
                    last_error = fix_error
                    break
                post_process_config = merge_post_process_configs(
                    prior_pp, post_process_config
                )

    post_process_config = merge_post_process_configs(prior_pp, post_process_config)
    exec_ms = int((time.perf_counter() - t0) * 1000)

    if last_error:
        ctx.trace.complete(
            "execute_query",
            PipelineStepStatus.FAILED,
            f"{last_error[:180]} ({exec_ms}ms)",
        )
        return ExecuteResult(
            sql=sql,
            narrative=narrative,
            post_process_config=post_process_config,
            columns=[],
            rows=[],
            row_count=0,
            raw_columns=None,
            raw_rows=None,
            raw_row_count=None,
            exec_ms=exec_ms,
            blocked_response=build_clarification("warehouse_execution_failed"),
        )

    ctx.trace.complete(
        "execute_query",
        PipelineStepStatus.COMPLETED,
        f"{row_count} rows ({exec_ms}ms)",
    )

    raw_columns: Optional[list[str]] = None
    raw_rows: Optional[list[list]] = None
    raw_row_count: Optional[int] = None

    if post_process_config:
        try:
            raw_columns = list(columns)
            raw_rows = [list(r) for r in rows]
            raw_row_count = row_count
            pp_after = validate_post_process_config(
                post_process_config,
                grounding=grounding,
                result_columns=raw_columns,
            )
            if pp_after:
                return ExecuteResult(
                    sql=sql,
                    narrative=narrative,
                    post_process_config=post_process_config,
                    columns=raw_columns,
                    rows=raw_rows,
                    row_count=raw_row_count or 0,
                    raw_columns=raw_columns,
                    raw_rows=raw_rows,
                    raw_row_count=raw_row_count,
                    exec_ms=exec_ms,
                    blocked_response=build_clarification("post_process_columns_mismatch"),
                )
            columns, rows = apply_post_processing(columns, rows, post_process_config)
            row_count = len(rows)
            rows = finalize_datamart_rows_after_post_process(rows, len(raw_rows))
            row_count = len(rows)
        except ValueError as exc:
            logger.warning("Post-processing failed: %s", exc)
            return ExecuteResult(
                sql=sql,
                narrative=narrative,
                post_process_config=post_process_config,
                columns=columns,
                rows=rows,
                row_count=row_count,
                raw_columns=raw_columns,
                raw_rows=raw_rows,
                raw_row_count=raw_row_count,
                exec_ms=exec_ms,
                partial_response=DatamartResponse(
                    question=question,
                    narrative=narrative,
                    sql=sql,
                    post_process_config=post_process_config,
                    columns=columns,
                    rows=rows,
                    row_count=row_count,
                    error=None,
                ),
            )

    narrative = enrich_narrative_from_results(
        question=question,
        narrative=narrative,
        columns=columns,
        rows=rows,
        intent=chat_intent,
    )

    return ExecuteResult(
        sql=sql,
        narrative=narrative,
        post_process_config=post_process_config,
        columns=columns,
        rows=rows,
        row_count=row_count,
        raw_columns=raw_columns,
        raw_rows=raw_rows,
        raw_row_count=raw_row_count,
        exec_ms=exec_ms,
    )
