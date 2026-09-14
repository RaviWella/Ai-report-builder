"""Helpers for logging grounded schema sent to the LLM."""
from __future__ import annotations

from ..semantic.column_projection import partition_columns
from ..schema_broker import SchemaGrounding


def grounding_columns_summary(grounding: SchemaGrounding) -> dict[str, list[str]]:
    """Compact per-table column lists for observability logs."""
    out: dict[str, list[str]] = {}
    for qualified, cols in (grounding.columns_by_table or {}).items():
        short = qualified.rsplit(".", 1)[-1]
        display, join_only = partition_columns(list(cols))
        tagged = [f"{c}*" for c in join_only[:12]]
        combined = display + tagged
        if len(join_only) > 12:
            combined.append(f"…+{len(join_only) - 12} join keys")
        out[short] = combined
    return out
