"""
Offline Tier A/B probe — same resolution order as ``sql_resolver`` without LLM.

Used by the chat runner to choose slim Tier-C prompts and by offline eval.
"""
from __future__ import annotations

from typing import Optional

from .. import config as dm_config
from ..orchestration.intent_router import ChatIntent
from ..domain_sql.metric_templates import try_resolve_verified_metric_sql
from ..orchestration.modify_mode import should_skip_deterministic_sql_shortcuts
from ..validation.pipeline_validation import PipelineValidationState
from ..domain_sql.report_spec import ReportSpec
from ..schema_broker import SchemaGrounding
from ..sql.sql_fast_path import try_resolve_deterministic_sql
from .artifacts import SqlArtifact
from .verified_query_store import retrieve_verified_sql, peek_verified_query_tables


def try_resolve_tier_ab(
    *,
    question: str,
    grounding: SchemaGrounding,
    chat_intent: ChatIntent,
    report_spec: Optional[ReportSpec],
    is_modify: bool,
    is_add_scenario: bool,
    targets: list[str],
    pval: PipelineValidationState,
    domain: str | None = None,
) -> Optional[SqlArtifact]:
    """
    Resolve SQL via Tier A or B only. Returns ``None`` when Tier C is required.
    """
    sql: Optional[str] = None
    narrative = ""
    sql_source: Optional[str] = None
    use_verified_metric = False

    if (
        dm_config.DATAMART_PREFER_DETERMINISTIC_SQL
        and not should_skip_deterministic_sql_shortcuts(
            is_modify=is_modify,
            is_add_scenario=is_add_scenario,
            targets=targets,
        )
        and chat_intent == ChatIntent.NEW_QUERY
    ):
        from ..schema_broker import ensure_grounding_includes_tables

        peek_tables = peek_verified_query_tables(
            question,
            domain=domain,
            min_score=4,
        )
        if peek_tables:
            grounding = ensure_grounding_includes_tables(grounding, list(peek_tables))

        vq = retrieve_verified_sql(
            question,
            grounded_tables=set(grounding.table_short_names),
            domain=domain,
            min_score=dm_config.DATAMART_VERIFIED_MIN_SCORE,
        )
        if vq:
            sql, sql_source, narrative = vq

    if (
        not sql
        and dm_config.DATAMART_PREFER_DETERMINISTIC_SQL
        and not should_skip_deterministic_sql_shortcuts(
            is_modify=is_modify,
            is_add_scenario=is_add_scenario,
            targets=targets,
        )
        and chat_intent == ChatIntent.NEW_QUERY
    ):
        resolved = try_resolve_deterministic_sql(
            question,
            grounding=grounding,
            report_spec=report_spec if dm_config.DATAMART_REPORT_SPEC_ENABLED else None,
        )
        if resolved:
            sql, sql_source, narrative = resolved

    if not sql and dm_config.DATAMART_VALIDATION_VERIFIED_METRICS and not is_add_scenario and not is_modify:
        verified = try_resolve_verified_metric_sql(question, retrieval=pval.retrieval)
        if verified:
            sql, _metric, narrative = verified
            use_verified_metric = True
            sql_source = "verified_metric"

    if not sql:
        return None

    from .sql_resolver import _is_catalog_source, _tier_label

    return SqlArtifact(
        sql=sql,
        narrative=narrative,
        post_process_config=None,
        source=sql_source,
        tier=_tier_label(sql_source),
        grounding=grounding,
        catalog_governed=_is_catalog_source(sql_source),
        use_verified_metric=use_verified_metric,
    )
