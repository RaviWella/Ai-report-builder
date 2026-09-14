"""Execute ADDITIONAL_RESULT_BLOCKS from a single chat turn (fast path)."""
from __future__ import annotations

import logging
from typing import Any, Optional

from ..llm.llm_response import validate_sql_syntax
from ..llm.llm_response import is_non_executable_sql
from ..models import DatamartResultBlock
from ..workspace.observability import log_extra_block
from ..postprocess.post_processor import (
    apply as apply_post_processing,
    finalize_datamart_rows_after_post_process,
    shrink_outer_limit_for_append_sql,
)
from ..postprocess.is_current_policy import apply_is_current_policy
from ..sql.sql_null_policy import apply_null_row_policy
from ..schema import execute_sql
from ..sql.sql_exec_guard import ensure_select_limit, is_warehouse_timeout_error
from ..schema_broker import SchemaGrounding
from ..sql.sql_exec_repairs import try_repair_sql_execution_error

logger = logging.getLogger("ai_services.datamart.extra_blocks")


def normalize_sql_one_line(sql: str) -> str:
    return " ".join(sql.strip().split())


def run_extra_datamart_block(
    *,
    spec: dict,
    system_prompt: str,
    primary_sql: str,
    question: str = "",
    grounding: Optional[SchemaGrounding] = None,
) -> DatamartResultBlock:
    """Run one extra SELECT. No LLM retries — deterministic SQL repair only."""
    del system_prompt  # kept for call-site compatibility

    block_id = str(spec.get("block_id") or "").strip()
    title_raw = spec.get("title")
    title = str(title_raw).strip() if title_raw is not None else None
    if title == "":
        title = None
    sql = (spec.get("sql") or spec.get("sql_script") or "").strip()
    post_process = spec.get("post_process")
    if post_process is None:
        post_process = spec.get("post_process_config")
    narrative = str(spec.get("narrative") or "").strip()

    if not block_id:
        return DatamartResultBlock(
            block_id="missing-id",
            title=title,
            narrative=narrative,
            sql=sql or None,
            post_process_config=post_process if isinstance(post_process, list) else None,
            error="Missing block_id in ADDITIONAL_RESULT_BLOCKS entry.",
        )
    if not sql:
        return DatamartResultBlock(
            block_id=block_id,
            title=title,
            narrative=narrative,
            sql=None,
            post_process_config=post_process if isinstance(post_process, list) else None,
            error="Missing sql in ADDITIONAL_RESULT_BLOCKS entry.",
        )
    if primary_sql.strip() and normalize_sql_one_line(sql) == normalize_sql_one_line(primary_sql):
        return DatamartResultBlock(
            block_id=block_id,
            title=title,
            narrative=narrative,
            sql=sql,
            post_process_config=post_process if isinstance(post_process, list) else None,
            error="Duplicate of primary SQL — omit this entry or use a different query.",
        )

    if not isinstance(post_process, list):
        post_process = None

    # Prefer governed templates for common roster patterns (add-scenario / extra blocks).
    if grounding and grounding.columns_by_table:
        from ..sql.sql_fast_path import try_resolve_deterministic_sql

        block_question = (title or question or "").strip()
        if block_question:
            resolved = try_resolve_deterministic_sql(block_question, grounding=grounding)
            if resolved:
                sql, _, narr = resolved
                if narr and not narrative:
                    narrative = narr

    # Treat SQL:NONE (or empty/non-SELECT) as missing — never return a block that invites execution.
    if is_non_executable_sql(sql):
        return DatamartResultBlock(
            block_id=block_id,
            title=title,
            narrative=narrative,
            sql=None,
            post_process_config=post_process,
            error="No valid SELECT query was produced for this added dataset.",
        )

    sql, _ = apply_is_current_policy(sql, question=question, grounding=grounding)
    sql, _ = apply_null_row_policy(sql, question=question)

    validation_error = validate_sql_syntax(sql)
    if validation_error:
        return DatamartResultBlock(
            block_id=block_id,
            title=title,
            narrative=narrative,
            sql=None if is_non_executable_sql(sql) else sql,
            post_process_config=post_process,
            error=f"SQL validation: {validation_error}",
        )

    columns: list[str] = []
    rows: list[list[Any]] = []
    row_count = 0
    last_error: Optional[str] = None

    for attempt in range(3):
        try:
            sql_run = ensure_select_limit(
                shrink_outer_limit_for_append_sql(sql, post_process)
            )
            columns, rows, row_count = execute_sql(sql_run, grounding)
            last_error = None
            if row_count == 0 and attempt < 2 and grounding:
                from ..semantic.column_value_peek import analyze_zero_row_filters

                zero_analysis = analyze_zero_row_filters(
                    sql_run, grounding.columns_by_table
                )
                if zero_analysis and zero_analysis.has_actionable_mismatch:
                    repaired = try_repair_zero_row_sql(sql_run, zero_analysis)
                    if repaired and repaired.strip() != sql_run.strip():
                        sql = repaired
                        continue
            log_extra_block(block_id, "sql_ok", attempt=attempt + 1, rows=row_count)
            break
        except RuntimeError as exc:
            last_error = str(exc)
            logger.warning("Extra block %s SQL failed: %s", block_id, last_error)
            if is_warehouse_timeout_error(last_error):
                break
            repaired = try_repair_sql_execution_error(sql, last_error, grounding)
            if repaired:
                sql = repaired
                continue
            break

    if last_error:
        return DatamartResultBlock(
            block_id=block_id,
            title=title,
            narrative=narrative,
            sql=sql,
            post_process_config=post_process,
            error=last_error,
        )

    raw_columns: Optional[list[str]] = None
    raw_rows: Optional[list[list[Any]]] = None
    raw_row_count: Optional[int] = None
    if post_process:
        try:
            raw_columns = list(columns)
            raw_rows = [list(r) for r in rows]
            raw_row_count = row_count
            columns, rows = apply_post_processing(columns, rows, post_process)
            row_count = len(rows)
            rows = finalize_datamart_rows_after_post_process(rows, len(raw_rows))
            row_count = len(rows)
        except ValueError as exc:
            return DatamartResultBlock(
                block_id=block_id,
                title=title,
                narrative=narrative,
                sql=sql,
                post_process_config=post_process,
                columns=columns,
                rows=rows,
                row_count=row_count,
                raw_columns=raw_columns,
                raw_rows=raw_rows,
                raw_row_count=raw_row_count,
                error=f"Post-processing warning: {exc}",
            )

    return DatamartResultBlock(
        block_id=block_id,
        title=title,
        narrative=narrative,
        sql=sql,
        post_process_config=post_process,
        columns=columns,
        rows=rows,
        row_count=row_count,
        raw_columns=raw_columns,
        raw_rows=raw_rows,
        raw_row_count=raw_row_count,
    )
