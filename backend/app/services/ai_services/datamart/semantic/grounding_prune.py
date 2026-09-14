"""
Prune and normalize schema grounding before LLM SQL generation.

Reduces binding failures when the catalog references dim_* tables that introspect
with few columns while mart_employee_current holds the user-facing fields.
"""
from __future__ import annotations

import re
from typing import Optional

from .column_projection import partition_columns
from ..schema_broker import SchemaGrounding

MART_EMPLOYEE_SHORT = "mart_employee_current"
DIM_EMPLOYEE_SHORT = "dim_employee"

# Tables with fewer display columns than this are dropped when mart covers employee master.
_MIN_DISPLAY_COLUMNS_KEEP = 6

_EMPLOYEE_MASTER_RE = re.compile(
    r"\b(?:employee|staff|workforce|probation|designation|manager|reporting|"
    r"department|branch|grade|active\s+employees?)\b",
    re.IGNORECASE,
)

# Catalog column on dim → mart physical column when both exist on mart.
_MART_COLUMN_REMAP: dict[str, str] = {
    "manager_emp_no": "superior_emp_no",
    "manager_name": "superior_fullname",
    "reporting_manager": "superior_fullname",
    "full_name": "emp_fullname",
    "employee_name": "emp_fullname",
    "emp_name": "emp_fullname",
    "employee_id": "emp_no",
    "emp_id": "emp_no",
}


def _display_column_count(columns: list[str]) -> int:
    display, _ = partition_columns(columns)
    return len(display)


def _qualified_for_short(grounding: SchemaGrounding, short: str) -> Optional[str]:
    low = short.lower()
    for q in grounding.qualified_tables:
        if q.rsplit(".", 1)[-1].lower() == low:
            return q
    return None


def _cols_for_short(grounding: SchemaGrounding, short: str) -> list[str]:
    q = _qualified_for_short(grounding, short)
    if not q:
        return []
    return list(grounding.columns_by_table.get(q) or [])


def _mart_has_column(grounding: SchemaGrounding, column: str) -> bool:
    cols = {c.lower() for c in _cols_for_short(grounding, MART_EMPLOYEE_SHORT)}
    col = column.lower()
    if col in cols:
        return True
    mapped = _MART_COLUMN_REMAP.get(col)
    return bool(mapped and mapped in cols)


def _remap_binding_table_column(
    table_short: str,
    column: str,
    grounding: SchemaGrounding,
) -> tuple[str, str]:
    """Prefer mart_employee_current when dim_employee lacks the catalog column."""
    t = table_short.lower()
    c = column.lower()
    if t == DIM_EMPLOYEE_SHORT and MART_EMPLOYEE_SHORT in {
        s.lower() for s in grounding.table_short_names
    }:
        mart_cols = {x.lower() for x in _cols_for_short(grounding, MART_EMPLOYEE_SHORT)}
        if c not in mart_cols:
            alt = _MART_COLUMN_REMAP.get(c)
            if alt and alt in mart_cols:
                return MART_EMPLOYEE_SHORT, alt
            if _mart_has_column(grounding, c):
                return MART_EMPLOYEE_SHORT, column
    return table_short, column


def filter_dimension_bindings(grounding: SchemaGrounding) -> SchemaGrounding:
    """Keep only bindings whose columns exist on the grounded table packet."""
    if not grounding.dimension_bindings:
        return grounding

    filtered: list[tuple[str, str, str]] = []
    for dim_name, table_short, column in grounding.dimension_bindings:
        table_short, column = _remap_binding_table_column(
            table_short, column, grounding
        )
        qualified = _qualified_for_short(grounding, table_short)
        if not qualified:
            continue
        allowed = {c.lower() for c in grounding.columns_by_table.get(qualified, [])}
        if column.lower() not in allowed:
            continue
        filtered.append((dim_name, table_short, column))

    grounding.dimension_bindings = filtered
    grounding.semantic_prompt_block = ""
    return grounding


def _drop_table(grounding: SchemaGrounding, short: str) -> SchemaGrounding:
    low = short.lower()
    new_map = {
        q: cols
        for q, cols in grounding.columns_by_table.items()
        if q.rsplit(".", 1)[-1].lower() != low
    }
    if len(new_map) == len(grounding.columns_by_table):
        return grounding
    shorts = [q.rsplit(".", 1)[-1] for q in new_map]
    from .join_hints import join_hints_for_tables
    from .semantic_layer import catalog_join_hints_for_tables

    hints = join_hints_for_tables(shorts)
    catalog_joins = catalog_join_hints_for_tables(shorts, columns_by_table=new_map)
    merged_hints = list(dict.fromkeys(hints + catalog_joins))
    grounding.columns_by_table = new_map
    grounding.join_hint_lines = merged_hints
    grounding.source = grounding.source + "+prune"
    return grounding


def prune_thin_employee_dimensions(
    grounding: SchemaGrounding,
    question: str,
) -> SchemaGrounding:
    """
    Drop dim_employee when mart_employee_current is grounded with richer columns.

    Prevents the LLM from joining a stub dim that only exposes ETL metadata columns.
    """
    if MART_EMPLOYEE_SHORT not in {s.lower() for s in grounding.table_short_names}:
        return grounding
    if DIM_EMPLOYEE_SHORT not in {s.lower() for s in grounding.table_short_names}:
        return grounding

    q = question or ""
    from ..domain_sql.employee_list_sql import looks_like_employee_detail_list

    if looks_like_employee_detail_list(q, grounding=grounding):
        return _drop_table(grounding, DIM_EMPLOYEE_SHORT)

    if not _EMPLOYEE_MASTER_RE.search(q):
        return grounding

    # Keep dim when user explicitly needs designation_id from dimension only.
    if re.search(r"\bdesignation\s+id\b", q, re.I) and not re.search(
        r"\bjob\s+title\b|\bdesignation\s+name\b", q, re.I
    ):
        return grounding

    mart_n = _display_column_count(_cols_for_short(grounding, MART_EMPLOYEE_SHORT))
    dim_n = _display_column_count(_cols_for_short(grounding, DIM_EMPLOYEE_SHORT))
    if dim_n >= _MIN_DISPLAY_COLUMNS_KEEP and dim_n >= mart_n - 2:
        return grounding

    return _drop_table(grounding, DIM_EMPLOYEE_SHORT)


def prune_grounding_for_sql(
    grounding: SchemaGrounding,
    question: str,
) -> SchemaGrounding:
    """Apply all grounding normalizations before building the LLM schema packet."""
    grounding = prune_thin_employee_dimensions(grounding, question)
    grounding = filter_dimension_bindings(grounding)
    from .dimension_enrich import enrich_grounding_with_dimensions

    grounding = enrich_grounding_with_dimensions(grounding, question=question)
    return grounding
