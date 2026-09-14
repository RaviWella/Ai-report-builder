"""
Shared SQL validation helpers for chat and template pipelines.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, Optional

from . import config as dm_config
from .domain_sql.leave_report_sql import (
    looks_like_leave_detail_report,
    try_build_leave_detail_report_sql,
)
from .domain_sql.payroll_report_sql import (
    looks_like_payroll_detail_report,
    try_build_payroll_detail_report_sql,
)
from .domain_sql.probation_report_sql import try_build_probation_report_sql
from .schema_broker import SchemaGrounding, expand_grounding_with_tables
from .sql.sql_binding import validate_sql_bindings
from .sql.sql_binding_rewrite import try_binding_catalog_rewrite
from .sql.sql_column_allowlist import try_rewrite_unknown_columns
from .sql.sql_join_semantics import try_repair_join_semantics, validate_join_semantics

logger = logging.getLogger("ai_services.datamart.pipeline")


def _rebuild_leave_sql_from_grounding(
    question: Optional[str],
    grounding: SchemaGrounding,
) -> Optional[str]:
    if not question or not looks_like_leave_detail_report(question):
        return None
    return try_build_leave_detail_report_sql(question, grounding=grounding)


def _rebuild_payroll_sql_from_grounding(
    question: Optional[str],
    grounding: SchemaGrounding,
) -> Optional[str]:
    if not question or not looks_like_payroll_detail_report(question):
        return None
    return try_build_payroll_detail_report_sql(question, grounding=grounding)


def _rebuild_probation_sql_from_grounding(
    question: Optional[str],
    grounding: SchemaGrounding,
) -> Optional[str]:
    if not question:
        return None
    return try_build_probation_report_sql(question, grounding=grounding)


def _binding_check(
    sql: str,
    grounding: SchemaGrounding,
    *,
    question: Optional[str],
) -> tuple[SchemaGrounding, Optional[str], str]:
    """
    Validate SQL against the broker grounding allowlist.

    IMPORTANT: By default we DO NOT expand the allowlist based on what the LLM wrote.
    Expanding from generated SQL can hide table-hallucination bugs and causes the
    user-visible failure to shift between different columns/tables on regenerate.
    """
    if dm_config.DATAMART_BINDING_EXPAND_FROM_SQL:
        grounding = expand_grounding_with_tables(grounding, sql)
    err = validate_sql_bindings(sql, grounding)
    if not err:
        repaired = try_repair_join_semantics(sql, grounding)
        if repaired and repaired.strip() != sql.strip():
            logger.info("Join semantics repaired before validation")
            sql = repaired
        err = validate_join_semantics(sql, grounding)
    if err and question:
        for rebuild_fn in (
            _rebuild_leave_sql_from_grounding,
            _rebuild_payroll_sql_from_grounding,
            _rebuild_probation_sql_from_grounding,
        ):
            rebuilt = rebuild_fn(question, grounding)
            if rebuilt and rebuilt.strip() != sql.strip():
                sql = rebuilt
                if dm_config.DATAMART_BINDING_EXPAND_FROM_SQL:
                    grounding = expand_grounding_with_tables(grounding, sql)
                err = validate_sql_bindings(sql, grounding)
                if not err:
                    break
    return grounding, err, sql


@dataclass
class SqlValidationOutcome:
    sql: str
    narrative: str
    post_process_config: Optional[list[dict]]
    grounding: SchemaGrounding
    error: Optional[str] = None
    grounding_expanded: bool = False


def validate_sql_with_grounding(
    *,
    sql: str,
    narrative: str,
    post_process_config: Optional[list[dict]],
    grounding: SchemaGrounding,
    system_prompt: str,
    retry_fn: Callable[..., tuple[str, str, Optional[list[dict]], Optional[str]]],
    allow_retry: bool = True,
    question: Optional[str] = None,
    skip_llm_binding_retry: bool = False,
) -> SqlValidationOutcome:
    """
    Binding check (with optional grounding expansion) + optional LLM retry on failure.
    ``retry_fn`` signature matches ``sql_retry.retry_on_error``.
    """
    tables_before = list(grounding.table_short_names)
    grounding, binding_error, sql = _binding_check(sql, grounding, question=question)

    if binding_error and question:
        rewritten = try_rewrite_unknown_columns(sql, grounding)
        if rewritten and rewritten.strip() != sql.strip():
            logger.info("Binding repaired via table-scoped column rewrite")
            sql = rewritten
            grounding, binding_error, sql = _binding_check(
                sql, grounding, question=question
            )

    if binding_error and question:
        rebuilt = _rebuild_leave_sql_from_grounding(question, grounding)
        if rebuilt:
            logger.info("Binding repaired via grounded leave catalog SQL")
            sql = rebuilt
            grounding, binding_error, sql = _binding_check(
                sql, grounding, question=question
            )
        if binding_error:
            rebuilt_probation = _rebuild_probation_sql_from_grounding(question, grounding)
            if rebuilt_probation:
                logger.info("Binding repaired via grounded probation catalog SQL")
                sql = rebuilt_probation
                grounding, binding_error, sql = _binding_check(
                    sql, grounding, question=question
                )
        if binding_error:
            catalog_sql = try_binding_catalog_rewrite(
                question,
                binding_error,
                sql=sql,
                grounding=grounding,
            )
            if catalog_sql:
                logger.info("Binding repaired via catalog SQL template (no LLM)")
                sql = catalog_sql
                grounding, binding_error, sql = _binding_check(
                    sql, grounding, question=question
                )

    if binding_error and allow_retry and not skip_llm_binding_retry:
        logger.warning("SQL binding failed: %s", binding_error)
        sql, narrative, post_process_config, fix_error = retry_fn(
            system_prompt=system_prompt,
            sql=sql,
            error=(
                f"Schema binding error: {binding_error}\n"
                "STRICT MODE: Do NOT introduce any new tables. Use ONLY the tables and columns "
                "present in the GROUNDED WAREHOUSE SCHEMA blocks. If a join key you want is not "
                "listed for that table, choose a different table from the grounded list or "
                "use a VALID JOIN PATH. Never join a label column (designation, full_name, "
                "*_name) to a surrogate key (*_sk) or mismatched id column."
            ),
            narrative=narrative,
            post_process_config=post_process_config,
        )
        if fix_error:
            return SqlValidationOutcome(
                sql=sql,
                narrative=narrative,
                post_process_config=post_process_config,
                grounding=grounding,
                error=fix_error,
            )
        grounding, binding_error, sql = _binding_check(
            sql, grounding, question=question
        )

    if binding_error:
        return SqlValidationOutcome(
            sql=sql,
            narrative=narrative,
            post_process_config=post_process_config,
            grounding=grounding,
            error=f"Generated SQL uses columns or tables not in the schema: {binding_error}",
            grounding_expanded=list(grounding.table_short_names) != tables_before,
        )

    return SqlValidationOutcome(
        sql=sql,
        narrative=narrative,
        post_process_config=post_process_config,
        grounding=grounding,
        grounding_expanded=list(grounding.table_short_names) != tables_before,
    )
