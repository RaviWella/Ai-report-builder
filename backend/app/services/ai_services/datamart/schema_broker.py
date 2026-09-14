"""
Schema broker — builds a grounded allowlist (tables + columns) for LLM prompts.

Replaces dumping the full mart DDL into the prompt. Used by chat and template pipelines.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from .config import (
    BROKER_MAX_COLUMNS_PER_TABLE,
    BROKER_MAX_PROMPT_CHARS,
    BROKER_MAX_TABLES,
    BROKER_MAX_TABLES_TOPIC,
    MAX_CONTEXT_TABLES,
    SEARCH_STOP_WORDS,
)
from .semantic.datahub import search_relevant_tables
from .orchestration.intent_router import ChatIntent
from .semantic.join_hints import join_hints_for_tables, related_table_short_names
from .schema import introspect_table_columns, list_warehouse_tables
from .semantic.semantic_layer import (
    SemanticResolution,
    catalog_join_hints_for_tables,
    required_tables_for_question,
    resolve_semantics,
)
from .sql.sql_refs import warehouse_introspection_keys_from_sql, warehouse_table_names_from_sql

logger = logging.getLogger("ai_services.datamart.broker")


class BrokerMode(str, Enum):
    CHAT = "chat"
    TEMPLATE = "template"


@dataclass
class SchemaGrounding:
    """Grounded schema contract passed to the LLM and SQL binding validator."""

    columns_by_table: dict[str, list[str]] = field(default_factory=dict)
    join_hint_lines: list[str] = field(default_factory=list)
    semantic_prompt_block: str = ""
    dimension_bindings: list[tuple[str, str, str]] = field(default_factory=list)
    topics_matched: list[str] = field(default_factory=list)
    metrics_matched: list[str] = field(default_factory=list)
    source: str = "introspection"

    @property
    def table_short_names(self) -> list[str]:
        return [qualified.rsplit(".", 1)[-1] for qualified in self.columns_by_table]

    @property
    def qualified_tables(self) -> list[str]:
        return list(self.columns_by_table.keys())

    def all_column_names(self) -> set[str]:
        names: set[str] = set()
        for cols in self.columns_by_table.values():
            for c in cols:
                names.add(c.lower())
        return names

    def allowlist_qualified_columns(self) -> set[str]:
        """Set of ``schema.table.column`` keys (lowercase) for binding checks."""
        keys: set[str] = set()
        for qualified, cols in self.columns_by_table.items():
            q_low = qualified.lower()
            for c in cols:
                keys.add(f"{q_low}.{c.lower()}")
        return keys

    def to_prompt_text(self) -> str:
        from .prompts.grounded_schema_prompt import format_grounded_schema_for_llm
        from .semantic.semantic_layer import SemanticResolution

        semantics: Optional[SemanticResolution] = None
        if self.dimension_bindings or self.topics_matched or self.metrics_matched:
            semantics = SemanticResolution(
                dimension_bindings=list(self.dimension_bindings),
                topics_matched=list(self.topics_matched),
                metrics_matched=list(self.metrics_matched),
            )
        return format_grounded_schema_for_llm(self, semantics=semantics)


def _tokens_from_text(text: str) -> set[str]:
    raw = re.findall(r"[a-z0-9_]+", text.lower())
    return {t for t in raw if t not in SEARCH_STOP_WORDS and len(t) > 2}


def _table_names_from_urns(urns: list[str]) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for urn in urns:
        try:
            dataset_part = urn.split(",")[1]
            short = dataset_part.split(".")[-1]
        except (IndexError, AttributeError):
            continue
        key = short.lower()
        if key in seen:
            continue
        seen.add(key)
        names.append(short)
        if len(names) >= BROKER_MAX_TABLES:
            break
    return names


def _rank_tables_by_keywords(question: str, all_tables: list[str], limit: int) -> list[str]:
    tokens = _tokens_from_text(question)
    if not tokens:
        return all_tables[:limit]

    scored: list[tuple[int, str]] = []
    for table in all_tables:
        tl = table.lower()
        parts = set(tl.split("_"))
        score = sum(2 for tok in tokens if tok in tl)
        score += sum(1 for tok in tokens if tok in parts)
        if tl.startswith("vw_"):
            score += 3
        if score > 0:
            scored.append((score, table))

    scored.sort(key=lambda x: (-x[0], x[1]))
    return [t for _, t in scored[:limit]]


_PAYROLL_TABLE_PRIORITY: tuple[str, ...] = (
    "vw_payroll_summary",
    "dim_employee",
    "dim_payroll_group",
    "snap_employee",
    "fact_payroll_detail",
    "fact_payroll",
    "mart_processed_payroll_summary",
    "dim_payroll_period",
    "vw_salary_bands",
    "fct_salary_change",
    "mart_salary_band_summary",
)

_ATTENDANCE_TABLE_PRIORITY: tuple[str, ...] = (
    "vw_attendance_summary",
    "mart_attendance_monthly_summary",
    "fact_attendance",
    "fct_daily_attendance",
    "dim_employee",
    "dim_shift",
)

_LEAVE_TABLE_PRIORITY: tuple[str, ...] = (
    "fact_leave_balance",
    "vw_leave_summary",
    "mart_employee_current",
    "dim_employee",
)

_BANK_TABLE_PRIORITY: tuple[str, ...] = (
    "mart_employee_current",
    "fct_salary_bank_instruction",
    "dim_bank",
    "dim_bank_branch",
    "dim_employee",
)

_SHIFT_TABLE_PRIORITY: tuple[str, ...] = (
    "mart_employee_current",
    "dim_shift",
    "snap_shift",
)

_RECRUITMENT_TABLE_PRIORITY: tuple[str, ...] = (
    "fact_recruitment_pipeline",
    "dim_candidate",
    "dim_job",
    "dim_org_unit",
)


def _broker_table_cap(semantics: SemanticResolution, question: str) -> int:
    """Allow more tables when the semantic catalog seeds a wide topic (e.g. payroll)."""
    q = question.lower()
    if re.search(r"\battendance\b", q):
        return BROKER_MAX_TABLES_TOPIC
    if "payroll" in (semantics.topics_matched or []) and re.search(r"\bpayroll\b", q):
        return BROKER_MAX_TABLES_TOPIC
    if "payroll summary" in q:
        return BROKER_MAX_TABLES_TOPIC
    if len(semantics.seed_tables) > BROKER_MAX_TABLES:
        return min(BROKER_MAX_TABLES_TOPIC, len(semantics.seed_tables))
    return BROKER_MAX_TABLES


def _prioritize_table_names(
    question: str,
    tables: list[str],
    topics_matched: list[str],
) -> list[str]:
    """Keep semantic seeds but surface the most relevant tables first under the cap."""
    q = question.lower()
    priority: list[str] = []
    if re.search(
        r"\b(?:recruitment|recruit|hiring|candidate|candidates|pipeline|linkedin|referral)\b",
        q,
    ):
        priority.extend(_RECRUITMENT_TABLE_PRIORITY)
    elif re.search(r"\bbank\b", q) and re.search(
        r"\b(?:employee|employees|staff|detail|details|account)\b", q
    ):
        priority.extend(_BANK_TABLE_PRIORITY)
    elif re.search(r"\bshift\b", q) and re.search(
        r"\b(?:employee|employees|staff|emp)\b", q
    ):
        priority.extend(_SHIFT_TABLE_PRIORITY)
    elif re.search(r"\battendance\b", q):
        priority.extend(_ATTENDANCE_TABLE_PRIORITY)
    elif re.search(r"\bleave\b", q):
        priority.extend(_LEAVE_TABLE_PRIORITY)
    elif "payroll" in topics_matched and re.search(r"\bpayroll\b", q) and not re.search(
        r"\bbank\b", q
    ):
        priority.extend(_PAYROLL_TABLE_PRIORITY)
    elif re.search(r"\bpayroll\b", q):
        priority.extend(_PAYROLL_TABLE_PRIORITY)
    if "snapshot" in q or "snap" in q.split():
        priority.extend(["snap_employee", "fact_employee_snapshot"])
    if "employee" in q or "employee_information" in topics_matched:
        priority.extend(["dim_employee", "mart_employee_current", "vw_headcount"])
    if "salary change" in q or re.search(r"\bsalary\s+change\b", q):
        priority.extend(["fct_salary_change", "mart_employee_current", "vw_salary_bands"])
    if re.search(r"\bsalary\s+band", q):
        priority.extend(
            ["vw_salary_bands", "mart_salary_band_summary", "mart_employee_current"]
        )
    if re.search(r"\bprobation\b", q):
        priority.extend(
            [
                "mart_employee_current",
                "dim_employee",
            ]
        )

    ordered: list[str] = []
    seen: set[str] = set()
    for name in priority + tables:
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(name)
    return ordered


def _merge_table_names(*lists: list[str], max_tables: Optional[int] = None) -> list[str]:
    cap = max_tables if max_tables is not None else BROKER_MAX_TABLES
    out: list[str] = []
    seen: set[str] = set()
    for lst in lists:
        for name in lst:
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(name)
            if len(out) >= cap:
                return out
    return out


def _columns_from_datahub_text(datahub_text: str) -> dict[str, list[str]]:
    """Parse ``get_columns_for_urns`` formatted lines into a column map."""
    out: dict[str, list[str]] = {}
    current: Optional[str] = None
    for line in datahub_text.splitlines():
        line = line.strip()
        if line.startswith("Table:"):
            current = line.replace("Table:", "").strip()
            out.setdefault(current, [])
        elif line.startswith("Columns:") and current:
            raw = line.replace("Columns:", "").strip()
            cols = [c.strip() for c in raw.split(",") if c.strip()]
            out[current] = cols
    return out


def _finalize_grounding(
    selected: list[str],
    *,
    semantics_prompt_block: str,
    source: str,
    dimension_bindings: Optional[list[tuple[str, str, str]]] = None,
    topics_matched: Optional[list[str]] = None,
    metrics_matched: Optional[list[str]] = None,
) -> SchemaGrounding:
    """Introspect warehouse columns for selected tables and attach join + semantic hints."""
    if not selected:
        return SchemaGrounding()

    col_map = introspect_table_columns(selected)
    if not col_map:
        logger.warning("Schema broker: introspection returned no columns for %s", selected)
        return SchemaGrounding()

    short_names = [q.rsplit(".", 1)[-1] for q in col_map]
    hints = join_hints_for_tables(short_names)
    catalog_joins = catalog_join_hints_for_tables(short_names)
    merged_hints = list(dict.fromkeys(hints + catalog_joins))
    logger.info("Schema broker: source=%s tables=%s", source, short_names)
    return SchemaGrounding(
        columns_by_table=col_map,
        join_hint_lines=merged_hints,
        semantic_prompt_block=semantics_prompt_block,
        dimension_bindings=list(dimension_bindings or []),
        topics_matched=list(topics_matched or []),
        metrics_matched=list(metrics_matched or []),
        source=source,
    )


def ensure_grounding_includes_tables(
    grounding: SchemaGrounding,
    table_short_names: list[str],
) -> SchemaGrounding:
    """Add missing catalog-required tables to the allowlist (retrieval repair)."""
    if not table_short_names:
        return grounding
    have = {s.lower() for s in grounding.table_short_names}
    missing = [t for t in table_short_names if t.lower() not in have]
    if not missing:
        return grounding
    merged = _merge_table_names(
        missing,
        grounding.table_short_names,
        related_table_short_names(missing),
    )
    expanded = _finalize_grounding(
        merged,
        semantics_prompt_block=grounding.semantic_prompt_block,
        source=grounding.source + "+required",
        dimension_bindings=grounding.dimension_bindings,
        topics_matched=grounding.topics_matched,
        metrics_matched=grounding.metrics_matched,
    )
    return expanded if expanded.columns_by_table else grounding


def expand_grounding_with_tables(
    grounding: SchemaGrounding,
    sql: str,
) -> SchemaGrounding:
    """Add tables referenced in ``sql`` (and related join partners) to the allowlist."""
    sql_keys = warehouse_introspection_keys_from_sql(sql)
    extra_short = warehouse_table_names_from_sql(sql)
    if not sql_keys and not extra_short:
        return grounding
    merged_short = _merge_table_names(grounding.table_short_names, extra_short)
    merged_short = _merge_table_names(merged_short, related_table_short_names(merged_short))
    have_short = {s.lower() for s in grounding.table_short_names}
    new_short = [s for s in merged_short if s.lower() not in have_short]
    if not sql_keys and not new_short:
        return grounding

    introspect_keys = list(dict.fromkeys(sql_keys + new_short))
    col_map = introspect_table_columns(introspect_keys)
    if not col_map:
        return grounding

    merged_cols = dict(grounding.columns_by_table)
    merged_cols.update(col_map)
    short_names = [q.rsplit(".", 1)[-1] for q in merged_cols]
    hints = join_hints_for_tables(short_names)
    catalog_joins = catalog_join_hints_for_tables(short_names)
    merged_hints = list(dict.fromkeys(grounding.join_hint_lines + hints + catalog_joins))
    return SchemaGrounding(
        columns_by_table=merged_cols,
        join_hint_lines=merged_hints,
        semantic_prompt_block=grounding.semantic_prompt_block,
        dimension_bindings=list(grounding.dimension_bindings),
        topics_matched=list(grounding.topics_matched),
        metrics_matched=list(grounding.metrics_matched),
        source=grounding.source + "+expand",
    )


def build_schema_grounding(
    *,
    question: str,
    mode: BrokerMode,
    template_sql: Optional[str] = None,
    last_sql: Optional[str] = None,
    seed_table_names: Optional[list[str]] = None,
    confirmed_table_names: Optional[list[str]] = None,
    chat_intent: Optional[ChatIntent] = None,
) -> SchemaGrounding:
    """
    Build a grounded schema packet for the LLM and SQL binding validator.

    Parameters
    ----------
    question:
        Current user message.
    mode:
        CHAT (discovery) vs TEMPLATE (tables from template SQL first).
    template_sql:
        Latest saved template SQL (template mode).
    last_sql:
        Previous turn SQL from session history (chat follow-ups).
    seed_table_names:
        Extra table short names (e.g. parsed from history SQL).
    """
    seed_from_sql: list[str] = []
    if template_sql:
        seed_from_sql.extend(warehouse_table_names_from_sql(template_sql))
    if last_sql:
        seed_from_sql.extend(warehouse_table_names_from_sql(last_sql))
    if seed_table_names:
        seed_from_sql.extend(seed_table_names)

    semantics = resolve_semantics(question)
    prioritized_seeds = _prioritize_table_names(
        question,
        semantics.seed_tables,
        semantics.topics_matched,
    )
    if prioritized_seeds:
        seed_from_sql = _merge_table_names(seed_from_sql, prioritized_seeds)

    table_cap = _broker_table_cap(semantics, question)
    selected: list[str] = []
    source = "introspection"
    intent = chat_intent or ChatIntent.NEW_QUERY
    refine_only = mode == BrokerMode.CHAT and intent in (
        ChatIntent.REFINE_SQL,
        ChatIntent.POST_PROCESS_ONLY,
        ChatIntent.ANALYTICAL_OVER_PRIOR,
    )
    must_include = list(
        required_tables_for_question(question, chat_intent=chat_intent)
    )

    if mode == BrokerMode.TEMPLATE and seed_from_sql:
        selected = _merge_table_names(seed_from_sql)
    elif refine_only and seed_from_sql:
        selected = _merge_table_names(
            seed_from_sql,
            related_table_short_names(seed_from_sql),
        )
        source = "refine"
    else:
        from . import config as dm_config

        catalog_first = dm_config.DATAMART_SCHEMA_CATALOG_FIRST
        catalog_seeds = _merge_table_names(
            must_include,
            prioritized_seeds,
            seed_from_sql,
            max_tables=table_cap,
        )
        if catalog_first and catalog_seeds and (must_include or prioritized_seeds):
            selected = _merge_table_names(
                catalog_seeds,
                related_table_short_names(catalog_seeds),
                max_tables=table_cap,
            )
            source = "broker+catalog"
        else:
            urns = search_relevant_tables(question)
            urn_tables = (
                _table_names_from_urns(urns[:MAX_CONTEXT_TABLES]) if urns else []
            )
            all_tables = list_warehouse_tables()
            ranked = _rank_tables_by_keywords(question, all_tables, table_cap)
            selected = _merge_table_names(
                must_include,
                prioritized_seeds,
                seed_from_sql,
                urn_tables,
                ranked,
                max_tables=table_cap,
            )
            selected = _merge_table_names(
                selected,
                related_table_short_names(selected),
                max_tables=table_cap,
            )
            source = "broker+datahub" if urn_tables else "broker"

    if confirmed_table_names:
        selected = _merge_table_names(
            confirmed_table_names,
            related_table_short_names(confirmed_table_names),
        )
        source = source + "+confirmed"

    if must_include:
        selected = _merge_table_names(
            must_include,
            selected,
            max_tables=table_cap,
        )

    if not selected:
        logger.warning("Schema broker: no tables selected for question=%r", question[:80])
        return SchemaGrounding()

    grounding = _finalize_grounding(
        selected,
        semantics_prompt_block=semantics.prompt_block,
        source=source,
        dimension_bindings=semantics.dimension_bindings,
        topics_matched=semantics.topics_matched,
        metrics_matched=semantics.metrics_matched,
    )
    if grounding.columns_by_table:
        from .semantic.dimension_enrich import enrich_grounding_with_dimensions
        from .semantic.grounding_prune import prune_grounding_for_sql

        grounding = enrich_grounding_with_dimensions(grounding, question=question)
        return prune_grounding_for_sql(grounding, question)

    if mode == BrokerMode.TEMPLATE:
        col_map = introspect_table_columns(None)
        col_map = {
            k: v
            for k, v in col_map.items()
            if k.rsplit(".", 1)[-1].lower() in {t.lower() for t in selected}
        }
        if col_map:
            short_names = [q.rsplit(".", 1)[-1] for q in col_map]
            return SchemaGrounding(
                columns_by_table=col_map,
                join_hint_lines=join_hints_for_tables(short_names),
                semantic_prompt_block=semantics.prompt_block,
                dimension_bindings=semantics.dimension_bindings,
                topics_matched=semantics.topics_matched,
                metrics_matched=semantics.metrics_matched,
                source=source + "+fallback",
            )

    return SchemaGrounding()
