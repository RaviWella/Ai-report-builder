"""Structured logging for datamart pipeline stages."""
from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger("ai_services.datamart.observability")


def log_pipeline_start(
    *,
    pipeline: str,
    question: str,
    intent: Optional[str] = None,
) -> None:
    logger.info(
        "datamart.pipeline.start pipeline=%s intent=%s question=%r",
        pipeline,
        intent or "-",
        question[:120],
    )


def log_retrieval_validation(
    *,
    pipeline: str,
    status: str,
    overall_tables: list[str],
) -> None:
    logger.info(
        "datamart.retrieval_validation pipeline=%s status=%s tables=%s",
        pipeline,
        status,
        overall_tables,
    )


def log_grounding(
    *,
    pipeline: str,
    source: str,
    tables: list[str],
    intent: Optional[str] = None,
) -> None:
    logger.info(
        "datamart.grounding pipeline=%s intent=%s source=%s tables=%s",
        pipeline,
        intent or "-",
        source,
        tables,
    )


def log_llm_response(*, pipeline: str, chars: int, parsed_sql: bool) -> None:
    logger.debug(
        "datamart.llm_response pipeline=%s chars=%d has_sql=%s",
        pipeline,
        chars,
        parsed_sql,
    )


def log_sql_execution(*, pipeline: str, attempt: int, row_count: int) -> None:
    logger.info(
        "datamart.sql_ok pipeline=%s attempt=%d rows=%d",
        pipeline,
        attempt,
        row_count,
    )


def log_binding_failure(*, pipeline: str, error: str) -> None:
    logger.warning("datamart.binding_failed pipeline=%s error=%s", pipeline, error)


def log_repair(*, kind: str, success: bool, detail: str = "") -> None:
    level = logging.INFO if success else logging.WARNING
    logger.log(level, "datamart.repair kind=%s success=%s %s", kind, success, detail)


def log_extra_block(block_id: str, event: str, **kwargs: Any) -> None:
    logger.info("datamart.extra_block block_id=%s event=%s %s", block_id, event, kwargs)


def log_llm_sql_generation_context(
    *,
    pipeline: str,
    question: str,
    grounding_source: str,
    tables: list[str],
    columns_by_table_summary: dict[str, list[str]],
    schema_context_chars: int,
    history_chars: int,
    user_prompt_chars: int,
    est_input_tokens: int,
    schema_context: str,
    user_prompt: str,
    max_logged_chars: int,
) -> None:
    """Log the exact DB context packet the LLM receives for SQL generation."""
    schema_logged = schema_context
    if len(schema_logged) > max_logged_chars:
        schema_logged = (
            schema_logged[:max_logged_chars]
            + f"\n\n[schema_context truncated for log — total {schema_context_chars} chars]"
        )
    prompt_logged = user_prompt
    if len(prompt_logged) > max_logged_chars:
        prompt_logged = (
            prompt_logged[:max_logged_chars]
            + f"\n\n[user_prompt truncated for log — total {user_prompt_chars} chars]"
        )

    logger.info(
        "datamart.llm_context pipeline=%s question=%r source=%s tables=%s "
        "schema_chars=%d history_chars=%d user_chars=%d est_tokens=%d",
        pipeline,
        question[:200],
        grounding_source,
        tables,
        schema_context_chars,
        history_chars,
        user_prompt_chars,
        est_input_tokens,
    )
    for table, cols in columns_by_table_summary.items():
        sample = ", ".join(cols[:24])
        if len(cols) > 24:
            sample += f", … (+{len(cols) - 24} more)"
        logger.info("datamart.llm_context.columns table=%s count=%d cols=%s", table, len(cols), sample)
    logger.info(
        "datamart.llm_context.schema_packet begin\n%s\ndatamart.llm_context.schema_packet end",
        schema_logged,
    )
    logger.info(
        "datamart.llm_context.user_prompt begin\n%s\ndatamart.llm_context.user_prompt end",
        prompt_logged,
    )
