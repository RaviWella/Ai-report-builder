"""
Format grounded schema for the LLM: per-schema / per-table blocks (no mixed column lists).

Reduces cross-table column hallucination (e.g. employee_id on the wrong mart).
"""
from __future__ import annotations

from collections import defaultdict
from typing import Optional

from ..config import BROKER_MAX_COLUMNS_PER_TABLE, BROKER_MAX_PROMPT_CHARS
from ..semantic.column_projection import format_column_lists_for_prompt, partition_columns
from ..schema_broker import SchemaGrounding
from ..semantic.semantic_layer import SemanticResolution, catalog_join_hints_for_tables
from ..sql.sql_column_allowlist import columns_by_table_short


def _group_tables_by_schema(columns_by_table: dict[str, list[str]]) -> dict[str, list[tuple[str, list[str]]]]:
    """schema_name -> [(qualified_table, columns), ...] sorted by table name."""
    by_schema: dict[str, list[tuple[str, list[str]]]] = defaultdict(list)
    for qualified, cols in sorted(columns_by_table.items(), key=lambda x: x[0].lower()):
        parts = qualified.split(".")
        if len(parts) >= 2:
            schema, table = parts[0], ".".join(parts[1:])
        else:
            schema, table = "public", parts[0]
        by_schema[schema].append((f"{schema}.{table}", cols))
    return dict(sorted(by_schema.items(), key=lambda x: x[0].lower()))


def _infer_join_pairs(
    left_q: str,
    left_cols: set[str],
    right_q: str,
    right_cols: set[str],
) -> list[str]:
    """Suggest join keys that exist on both tables (exact name match)."""
    pairs: list[str] = []
    priority = (
        "employee_sk",
        "employee_id",
        "employee_no",
        "emp_no",
        "source_bank_id",
        "source_bank_branch_id",
        "payroll_period_sk",
        "source_payroll_group_id",
        "leave_type_id",
        "source_shift_id",
        "source_desig_id",
        "candidate_id",
        "leave_type_id",
        "designation_id",
        "payroll_group_id",
        "branch_id",
        "department_id",
    )
    used: set[tuple[str, str]] = set()
    for key in priority:
        if key in left_cols and key in right_cols:
            used.add((key, key))
            pairs.append(f"  {left_q}.{key} = {right_q}.{key}")
    for col in sorted(left_cols & right_cols):
        if col.endswith("_sk") or col.endswith("_id"):
            if (col, col) not in used:
                pairs.append(f"  {left_q}.{col} = {right_q}.{col}")
    return pairs[:6]


def build_validated_join_lines(grounding: SchemaGrounding) -> list[str]:
    """Join hints where both columns exist on the grounded tables."""
    if not grounding.columns_by_table:
        return []
    short_names = grounding.table_short_names
    cols_short = columns_by_table_short(grounding)
    lines: list[str] = []

    for line in catalog_join_hints_for_tables(
        short_names,
        columns_by_table=grounding.columns_by_table,
    ):
        lines.append(f"  · {line}")

    for line in grounding.join_hint_lines or []:
        stripped = line.strip()
        if stripped and stripped not in {l.replace("  · ", "") for l in lines}:
            lines.append(f"  · {stripped}")

    qualified = list(grounding.columns_by_table.keys())
    inferred: list[str] = []
    for i, left_q in enumerate(qualified):
        left_short = left_q.rsplit(".", 1)[-1].lower()
        left_cols = cols_short.get(left_short, set())
        for right_q in qualified[i + 1 :]:
            right_short = right_q.rsplit(".", 1)[-1].lower()
            right_cols = cols_short.get(right_short, set())
            for pair in _infer_join_pairs(left_q, left_cols, right_q, right_cols):
                inferred.append(pair)
    if inferred:
        lines.append("  · Inferred keys (both columns exist on these tables):")
        lines.extend(inferred[:8])

    return lines


def build_table_scoped_semantic_lines(
    semantics: SemanticResolution,
    grounding: SchemaGrounding,
) -> list[str]:
    """Business-term mappings only for tables present in this grounding packet."""
    if not semantics.dimension_bindings:
        return []
    grounded_shorts = {q.rsplit(".", 1)[-1].lower() for q in grounding.columns_by_table}
    by_table: dict[str, list[str]] = defaultdict(list)
    for dim_name, table_short, column in semantics.dimension_bindings:
        if table_short.lower() not in grounded_shorts:
            continue
        qualified = next(
            (q for q in grounding.columns_by_table if q.rsplit(".", 1)[-1].lower() == table_short.lower()),
            table_short,
        )
        allowed_cols = {c.lower() for c in grounding.columns_by_table.get(qualified, [])}
        if column.lower() not in allowed_cols:
            continue
        label = dim_name.replace("_", " ")
        by_table[qualified].append(f'    "{label}" → {column}')

    if not by_table:
        return []

    lines = [
        "BUSINESS TERMS (use only on the table shown — never copy a column to another table):",
    ]
    for qualified in sorted(by_table.keys(), key=str.lower):
        lines.append(f"  [{qualified}]")
        lines.extend(by_table[qualified][:8])
    if semantics.metrics_matched:
        lines.append(f"  Metrics referenced: {', '.join(semantics.metrics_matched[:6])}")
    if semantics.topics_matched:
        lines.append(f"  Topics: {', '.join(semantics.topics_matched[:6])}")
    return lines


def format_grounded_schema_for_llm(
    grounding: SchemaGrounding,
    *,
    semantics: Optional[SemanticResolution] = None,
) -> str:
    """Structured allowlist text for the LLM user message."""
    if not grounding.columns_by_table:
        return "GROUNDED SCHEMA: (no tables selected — explain in NARRATIVE and use SQL:NONE)."

    lines: list[str] = [
        "=== GROUNDED WAREHOUSE SCHEMA ===",
        "Rules:",
        "1. Use ONLY the tables and columns listed below — do not invent names.",
        "2. Each alias in SQL maps to exactly ONE table block below.",
        "3. A column may appear in SQL only if it is listed under THAT table (or qualified as schema.table.column).",
        "4. Use JOIN/WHERE-only columns for joins and filters, not in SELECT unless the user asked for that id.",
        "5. For joins, use VALID JOIN PATHS or keys listed under both tables — never assume a key exists on both sides.",
        "6. Never join a label column (designation, full_name, *_name) to a surrogate key (*_sk) or a different id column.",
        "",
    ]

    grouped = _group_tables_by_schema(grounding.columns_by_table)
    table_index = 0
    for schema_name, tables in grouped.items():
        lines.append(f"--- SCHEMA: {schema_name} ---")
        for qualified, cols in tables:
            table_index += 1
            short = qualified.rsplit(".", 1)[-1]
            display, join_only = partition_columns(cols)
            lines.append(f"[T{table_index}] TABLE: {qualified}")
            lines.append(f"  Short name: {short}  (use unique alias, e.g. t{table_index} or a short mnemonic)")
            lines.extend(
                format_column_lists_for_prompt(
                    display,
                    join_only,
                    max_display=BROKER_MAX_COLUMNS_PER_TABLE,
                    max_join=32,
                )
            )
            lines.append("")

    join_lines = build_validated_join_lines(grounding)
    if join_lines:
        lines.append("--- VALID JOIN PATHS (verified columns on grounded tables) ---")
        lines.extend(join_lines)
        lines.append("")

    if semantics:
        sem_lines = build_table_scoped_semantic_lines(semantics, grounding)
        if sem_lines:
            lines.extend(sem_lines)
            lines.append("")
    elif grounding.semantic_prompt_block and semantics is None:
        # Unfiltered catalog text is omitted when dimension_bindings are used (see grounding_prune).
        lines.append("--- SEMANTIC NOTES ---")
        lines.append(grounding.semantic_prompt_block)
        lines.append("")

    text = "\n".join(lines).strip()
    if len(text) > BROKER_MAX_PROMPT_CHARS:
        return text[:BROKER_MAX_PROMPT_CHARS].rstrip() + "\n\n[Grounded schema truncated — use tables listed above only.]"
    return text
