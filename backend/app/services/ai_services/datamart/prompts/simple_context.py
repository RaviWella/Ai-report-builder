"""
Build LLM context for the simplified datamart chat flow.

1. Top catalog mappings from semantic YAML (topics, dimensions, metrics)
2. DataHub metadata search + column descriptions
3. Live warehouse column introspection for selected tables
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..semantic.column_value_peek import format_sample_values_block
from ..config import BROKER_MAX_TABLES, MAX_CONTEXT_TABLES
from ..semantic.datahub import get_columns_for_urns, search_relevant_tables
from ..schema import introspect_table_columns, list_warehouse_tables
from ..semantic.join_hints import join_hints_for_tables, related_table_short_names
from ..schema_broker import (
    SchemaGrounding,
    _merge_table_names,
    _rank_tables_by_keywords,
    _table_names_from_urns,
)
from ..semantic.semantic_layer import _load_catalog, resolve_semantics
from ..sql.sql_refs import warehouse_table_names_from_sql


@dataclass
class SimpleChatContext:
    mappings_text: str
    datahub_text: str
    schema_text: str
    grounding: SchemaGrounding
    table_short_names: list[str]


def format_top_catalog_mappings(question: str, *, limit: int = 5) -> tuple[str, list[str]]:
    """Return formatted mapping block and table short names referenced."""
    semantics = resolve_semantics(question)
    catalog = _load_catalog()
    scored: list[tuple[int, str, list[str]]] = []

    topics_block = catalog.get("topics") or {}
    for i, topic in enumerate(semantics.topics_matched):
        spec = topics_block.get(topic) or {}
        tables = [t for t in (spec.get("tables") or []) if isinstance(t, str)]
        desc = str(spec.get("description") or "").strip()
        block = (
            f"Topic: {topic}\n"
            f"  Description: {desc or '(see catalog)'}\n"
            f"  Tables: {', '.join(tables[:10])}"
        )
        scored.append((100 - i, block, tables))

    for i, (dim, table, column) in enumerate(semantics.dimension_bindings):
        block = f"Dimension: {dim}\n  Column: {table}.{column}"
        scored.append((95 - i, block, [table]))

    metrics_block = catalog.get("metrics") or {}
    for i, metric in enumerate(semantics.metrics_matched):
        spec = metrics_block.get(metric) or {}
        tables = [t for t in (spec.get("tables") or []) if isinstance(t, str)]
        desc = str(spec.get("description") or "").strip()
        block = (
            f"Metric: {metric}\n"
            f"  Description: {desc or '(see catalog)'}\n"
            f"  Tables: {', '.join(tables[:8])}"
        )
        scored.append((85 - i, block, tables))

    scored.sort(key=lambda x: -x[0])
    picked = scored[:limit]
    if not picked:
        return (
            "(No strong catalog matches — rely on DataHub search and warehouse schema below.)",
            [],
        )

    text = "\n\n".join(block for _, block, _ in picked)
    tables: list[str] = []
    for _, _, tlist in picked:
        tables.extend(tlist)
    return text, tables


def _keyword_extra_tables(question: str) -> list[str]:
    """Proactively add tables often needed but missing from keyword search."""
    q = (question or "").lower()
    extras: list[str] = []
    if re.search(r"\bemployees?\b|\bstaff\b|\bworkforce\b", q):
        extras.append("mart_employee_current")
    if re.search(r"\bbank\b", q):
        extras.extend(
            [
                "fct_salary_bank_instruction",
                "dim_bank",
                "dim_bank_branch",
                "mart_employee_current",
            ]
        )
    if re.search(r"\battendance\b", q):
        extras.extend(
            [
                "vw_attendance_summary",
                "fact_attendance",
                "mart_employee_current",
            ]
        )
    if re.search(r"\bleave\b|\bpending\b|\bapproval\b|\bcoverup\b|\bcover up\b", q):
        extras.extend(
            [
                "vw_leave_summary",
                "vw_pending_leave_approvals",
                "fact_leave_balance",
                "fact_leave_transaction",
                "mart_employee_current",
            ]
        )
    if re.search(r"\bpayroll\b|\bpayslip\b|\bsalary\b", q):
        extras.extend(["vw_payroll_summary", "mart_employee_current"])
    if re.search(r"\bshift\b", q):
        extras.extend(["dim_shift", "mart_employee_current"])
    if re.search(r"\bapproval\b|\bgroup\b", q) and re.search(r"\battendance\b", q):
        extras.extend(["mart_employee_current", "fact_attendance", "dim_org_unit"])
    return list(dict.fromkeys(extras))


def _tables_suggested_by_error(sql: str | None, error: str) -> list[str]:
    """Infer extra tables to introspect after a failed SQL attempt."""
    from ..sql.sql_recovery import diagnose_sql_failure, tables_for_recovery

    issue = diagnose_sql_failure(sql, error)
    return tables_for_recovery(issue, sql)


def _format_introspected_schema(
    columns_by_table: dict[str, list[str]],
    *,
    max_cols_per_table: int = 48,
    table_short_names: list[str] | None = None,
) -> str:
    if not columns_by_table:
        return "(Warehouse introspection returned no columns.)"
    lines: list[str] = []
    for qualified, cols in columns_by_table.items():
        shown = cols[:max_cols_per_table]
        col_str = ", ".join(shown)
        if len(cols) > max_cols_per_table:
            col_str += f", ... (+{len(cols) - max_cols_per_table} more)"
        lines.append(f"{qualified}\n  columns: {col_str}")

    shorts = table_short_names or [
        q.rsplit(".", 1)[-1] for q in columns_by_table
    ]
    hints = join_hints_for_tables(shorts)
    if hints:
        lines.append("\n## Join hints\n" + "\n".join(hints[:10]))
    sample_block = format_sample_values_block(
        columns_by_table,
        focus_tables=table_short_names,
    )
    if sample_block:
        lines.append("\n" + sample_block)
    return "\n\n".join(lines)


def _build_context_from_tables(
    question: str,
    selected: list[str],
    *,
    mappings_text: str,
    datahub_text: str,
    semantics_topics: list[str],
    semantics_metrics: list[str],
    dimension_bindings: list[tuple[str, str, str]],
    source_suffix: str = "",
) -> SimpleChatContext:
    col_map = introspect_table_columns(selected) if selected else {}
    shorts = [q.rsplit(".", 1)[-1] for q in col_map]
    grounding = SchemaGrounding(
        columns_by_table=col_map,
        join_hint_lines=join_hints_for_tables(shorts),
        source=f"simple:datahub+catalog+introspection{source_suffix}",
        topics_matched=list(semantics_topics),
        metrics_matched=list(semantics_metrics),
        dimension_bindings=list(dimension_bindings),
    )
    return SimpleChatContext(
        mappings_text=mappings_text,
        datahub_text=datahub_text,
        schema_text=_format_introspected_schema(col_map, table_short_names=shorts),
        grounding=grounding,
        table_short_names=grounding.table_short_names,
    )


def expand_simple_chat_context(
    ctx: SimpleChatContext,
    question: str,
    *,
    extra_tables: list[str] | None = None,
    max_tables: int = 16,
) -> SimpleChatContext:
    """Re-introspect with additional tables after a failed SQL attempt."""
    extras = list(extra_tables or [])
    extras.extend(_keyword_extra_tables(question))
    merged = _merge_table_names(
        ctx.table_short_names,
        extras,
        related_table_short_names(extras),
        max_tables=max_tables,
    )
    if merged == ctx.table_short_names and not extras:
        return ctx
    return _build_context_from_tables(
        question,
        merged,
        mappings_text=ctx.mappings_text,
        datahub_text=ctx.datahub_text,
        semantics_topics=ctx.grounding.topics_matched,
        semantics_metrics=ctx.grounding.metrics_matched,
        dimension_bindings=ctx.grounding.dimension_bindings,
        source_suffix="+expanded",
    )


def build_simple_chat_context(
    question: str,
    *,
    max_tables: int | None = None,
    mapping_limit: int = 5,
) -> SimpleChatContext:
    """Gather catalog mappings, DataHub metadata, and introspected warehouse schema."""
    cap = max_tables or min(BROKER_MAX_TABLES, 14)
    mappings_text, mapping_tables = format_top_catalog_mappings(
        question, limit=mapping_limit
    )

    urns = search_relevant_tables(question)
    datahub_text = get_columns_for_urns(urns)
    datahub_tables = _table_names_from_urns(urns[:MAX_CONTEXT_TABLES])

    semantics = resolve_semantics(question)
    seed_tables = list(semantics.seed_tables)
    keyword_tables = _keyword_extra_tables(question)

    ranked: list[str] = []
    all_tables = list_warehouse_tables()
    if all_tables:
        ranked = _rank_tables_by_keywords(question, all_tables, cap)

    selected = _merge_table_names(
        keyword_tables,
        mapping_tables,
        datahub_tables,
        seed_tables,
        related_table_short_names(keyword_tables + mapping_tables[:4]),
        ranked,
        max_tables=cap,
    )

    if not selected and ranked:
        selected = ranked[:cap]

    return _build_context_from_tables(
        question,
        selected,
        mappings_text=mappings_text,
        datahub_text=datahub_text or "(DataHub unavailable or returned no datasets.)",
        semantics_topics=list(semantics.topics_matched),
        semantics_metrics=list(semantics.metrics_matched),
        dimension_bindings=list(semantics.dimension_bindings),
    )
