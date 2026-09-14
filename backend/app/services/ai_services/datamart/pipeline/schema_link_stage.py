"""
S1 schema link stage: domain classify → table link → column load → link gate.

Replaces ad-hoc grounding patches and is the single entry for retrieval before SQL.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import re

from .. import config as dm_config
from ..orchestration.intent_router import ChatIntent
from ..domain_sql.report_spec import ReportDomain, ReportSpec, spec_required_tables
from ..schema_broker import (
    BrokerMode,
    SchemaGrounding,
    build_schema_grounding,
    ensure_grounding_includes_tables,
)
from ..semantic.join_hints import related_table_short_names
from ..semantic.semantic_layer import SemanticResolution, resolve_semantics, _load_catalog
from ..validation.validation_models import ValidationStatus
from .domain import DatamartDomain
from .domain_classifier import DomainClassification, classify_domain
from .domain_registry import (
    allowed_tables_for_domain,
    required_tables_for_domain,
)
from .verified_query_store import peek_verified_query_tables

logger = logging.getLogger("ai_services.datamart.schema_link")


@dataclass(frozen=True, slots=True)
class SchemaLinkInput:
    question: str
    chat_intent: ChatIntent
    broker_last_sql: Optional[str]
    confirmed_table_names: Optional[list[str]]
    report_spec: Optional[ReportSpec]


@dataclass
class SchemaLinkResult:
    grounding: SchemaGrounding
    domain: DomainClassification
    missing_required: list[str]
    gate_status: ValidationStatus
    gate_message: Optional[str]


def _report_spec_domain(spec: Optional[ReportSpec]) -> Optional[DatamartDomain]:
    if not spec:
        return None
    mapping = {
        ReportDomain.PAYROLL: DatamartDomain.PAYROLL,
        ReportDomain.LEAVE: DatamartDomain.LEAVE,
        ReportDomain.ATTENDANCE: DatamartDomain.ATTENDANCE,
        ReportDomain.WORKFORCE: DatamartDomain.WORKFORCE,
        ReportDomain.ATTRITION: DatamartDomain.ATTRITION,
    }
    return mapping.get(spec.domain)


def _must_include_tables(
    domain: DatamartDomain,
    *,
    report_spec: Optional[ReportSpec],
    confirmed: Optional[list[str]],
) -> list[str]:
    seeds: list[str] = []
    for t in required_tables_for_domain(domain):
        seeds.append(t)
    if report_spec:
        seeds.extend(spec_required_tables(report_spec))
    if confirmed:
        seeds.extend(confirmed)
    return seeds


def _catalog_must_include_tables(
    question: str,
    *,
    domain: DatamartDomain,
    semantics: SemanticResolution,
    report_spec: Optional[ReportSpec],
    confirmed: Optional[list[str]],
) -> list[str]:
    """
    Merge domain requirements with semantic catalog mappings so broker + prune
  keep tables tied to dimension bindings, topics, metrics, and verified SQL.
    """
    out: list[str] = []
    seen: set[str] = set()

    def add(name: str) -> None:
        key = (name or "").strip().lower()
        if not key or key in seen:
            return
        seen.add(key)
        out.append(name.strip())

    for t in _must_include_tables(domain, report_spec=report_spec, confirmed=confirmed):
        add(t)
    for t in semantics.seed_tables:
        add(t)
    for _dim, table, _column in semantics.dimension_bindings:
        add(table)
    catalog = _load_catalog()
    metrics_block = catalog.get("metrics") or {}
    for metric_name in semantics.metrics_matched:
        spec = metrics_block.get(metric_name) or {}
        for t in spec.get("tables") or []:
            if isinstance(t, str):
                add(t)
    domain_tag = (
        None
        if domain in (DatamartDomain.UNKNOWN, DatamartDomain.MIXED)
        else domain.value
    )
    peek_tables = peek_verified_query_tables(question, domain=domain_tag, min_score=4)
    for t in peek_tables:
        add(t)
    # Join partners for core seeds only — expanding related() over the full semantic
    # seed list can pull 50+ tables and stall remote introspection.
    related_seeds = list(
        dict.fromkeys(
            list(_must_include_tables(domain, report_spec=report_spec, confirmed=confirmed))
            + list(peek_tables)
            + list(confirmed or []),
        )
    )
    for t in related_table_short_names(related_seeds):
        add(t)
    cap = max(12, dm_config.BROKER_MAX_TABLES * 2)
    return out[:cap]


def _refine_expand_tables(question: str) -> list[str]:
    """
    When the user modifies a prior query, still load tables implied by the
    follow-up (e.g. add bank details → salary bank fact + bank dims).
    """
    q = (question or "").lower()
    out: list[str] = []
    if re.search(r"\bbank\b", q) and re.search(
        r"\b(?:detail|details|code|name|account|passbook|include|add)\b", q
    ):
        out.extend(
            [
                "mart_employee_current",
                "fct_salary_bank_instruction",
                "dim_bank",
                "dim_bank_branch",
                "dim_employee",
            ]
        )
    if re.search(r"\bshift\b", q):
        out.extend(["mart_employee_current", "dim_shift", "dim_employee"])
    return list(dict.fromkeys(out))


def _prune_to_domain_allowlist(
    grounding: SchemaGrounding,
    domain: DatamartDomain,
    *,
    max_tables: int,
    protected_short_names: frozenset[str] | None = None,
) -> SchemaGrounding:
    allow = allowed_tables_for_domain(domain)
    if not allow:
        return grounding

    required = {t.lower() for t in required_tables_for_domain(domain)}
    protected = {t.lower() for t in (protected_short_names or ())}
    kept: dict[str, list[str]] = {}
    for qualified, cols in grounding.columns_by_table.items():
        short = qualified.rsplit(".", 1)[-1].lower()
        if short in allow or short in required or short in protected:
            kept[qualified] = cols

    if not kept:
        return grounding

    if len(kept) > max_tables:
        # Prefer domain-required, then catalog-protected, then broker order.
        ordered: list[tuple[str, list[str]]] = []
        for q, c in grounding.columns_by_table.items():
            if q in kept:
                short = q.rsplit(".", 1)[-1].lower()
                if short in required:
                    pri = 0
                elif short in protected:
                    pri = 1
                else:
                    pri = 2
                ordered.append((short, pri, q, c))
        ordered.sort(key=lambda x: (x[1], x[0]))
        kept = {q: c for _, _, q, c in ordered[:max_tables]}

    if len(kept) == len(grounding.columns_by_table):
        return grounding

    shorts = [q.rsplit(".", 1)[-1] for q in kept]
    from ..semantic.join_hints import join_hints_for_tables

    return SchemaGrounding(
        columns_by_table=kept,
        join_hint_lines=join_hints_for_tables(shorts),
        semantic_prompt_block=grounding.semantic_prompt_block,
        dimension_bindings=list(grounding.dimension_bindings),
        topics_matched=list(grounding.topics_matched),
        metrics_matched=list(grounding.metrics_matched),
        source=grounding.source + f"+domain_{domain.value}",
    )


def _evaluate_link_gate(
    grounding: SchemaGrounding,
    domain: DatamartDomain,
) -> tuple[ValidationStatus, list[str], Optional[str]]:
    if not grounding.columns_by_table:
        return (
            ValidationStatus.INSUFFICIENT,
            [],
            "No schema columns could be loaded for this question.",
        )

    if domain in (DatamartDomain.UNKNOWN, DatamartDomain.MIXED):
        return ValidationStatus.SUFFICIENT, [], None

    required = [t.lower() for t in required_tables_for_domain(domain)]
    selected = {t.lower() for t in grounding.table_short_names}
    missing = [t for t in required if t not in selected]
    if missing:
        return (
            ValidationStatus.INSUFFICIENT,
            missing,
            "Schema link missing required tables for "
            f"{domain.value}: {', '.join(missing)}.",
        )
    return ValidationStatus.SUFFICIENT, [], None


def link_schema_for_turn(inp: SchemaLinkInput) -> SchemaLinkResult:
    semantics = resolve_semantics(inp.question)
    spec_domain = _report_spec_domain(inp.report_spec)
    classified = classify_domain(
        inp.question,
        topics_matched=semantics.topics_matched,
    )

    domain = spec_domain or classified.domain
    if spec_domain and classified.domain not in (
        DatamartDomain.UNKNOWN,
        DatamartDomain.MIXED,
        spec_domain,
    ):
        # ReportSpec can mis-tag recruitment as workforce ("employee referrals").
        if (
            spec_domain == DatamartDomain.WORKFORCE
            and classified.domain == DatamartDomain.RECRUITMENT
        ):
            domain = DatamartDomain.RECRUITMENT
        else:
            domain = spec_domain

    refine_only = inp.chat_intent in (
        ChatIntent.REFINE_SQL,
        ChatIntent.POST_PROCESS_ONLY,
        ChatIntent.ANALYTICAL_OVER_PRIOR,
    )

    if refine_only:
        catalog_must_include = _refine_expand_tables(inp.question)
    else:
        catalog_must_include = _catalog_must_include_tables(
            inp.question,
            domain=domain,
            semantics=semantics,
            report_spec=inp.report_spec,
            confirmed=inp.confirmed_table_names,
        )

    grounding = build_schema_grounding(
        question=inp.question,
        mode=BrokerMode.CHAT,
        last_sql=inp.broker_last_sql,
        chat_intent=inp.chat_intent,
        seed_table_names=catalog_must_include or None,
        confirmed_table_names=inp.confirmed_table_names,
    )

    if catalog_must_include:
        grounding = ensure_grounding_includes_tables(grounding, catalog_must_include)

    protected = frozenset(t.lower() for t in catalog_must_include)

    if domain not in (DatamartDomain.UNKNOWN, DatamartDomain.MIXED):
        cap = (
            dm_config.BROKER_MAX_TABLES_TOPIC
            if domain != DatamartDomain.WORKFORCE
            else dm_config.BROKER_MAX_TABLES
        )
        grounding = _prune_to_domain_allowlist(
            grounding,
            domain,
            max_tables=cap,
            protected_short_names=protected,
        )
        # Re-apply catalog + domain required tables after prune (never drop mappings).
        reinclude = list(
            dict.fromkeys(
                catalog_must_include
                + list(required_tables_for_domain(domain)),
            ),
        )
        grounding = ensure_grounding_includes_tables(grounding, reinclude)

    gate_status, missing, gate_message = _evaluate_link_gate(grounding, domain)

    logger.info(
        "schema_link domain=%s confidence=%.2f tables=%s gate=%s missing=%s",
        domain.value,
        classified.confidence,
        grounding.table_short_names[:8],
        gate_status.value,
        missing,
    )

    return SchemaLinkResult(
        grounding=grounding,
        domain=DomainClassification(
            domain=domain,
            confidence=classified.confidence,
            scores=classified.scores,
        ),
        missing_required=missing,
        gate_status=gate_status,
        gate_message=gate_message,
    )
