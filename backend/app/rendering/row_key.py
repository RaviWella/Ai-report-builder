"""Shared by excel_renderer.py and pdf_renderer.py: which key in a result row
dict holds a given output column's value.
"""

from __future__ import annotations


def resolve_row_key(data_row: dict, keys: list[str], ci: int, ref: str, label: str) -> str:
    """`col_refs`/`presentation.columns` can be in a DIFFERENT order than a
    result row dict's own keys (the SQL SELECT — and so each row's key order —
    follows dataSpec.fields' order, which the export's presentation-column
    order doesn't always mirror, e.g. after reordering columns in the
    builder). Matching a plain positional index (`keys[ci]`) into a
    differently-ordered row silently shifts every value into the wrong
    column. Match by identity first (the ref, or the label — which IS the
    actual SQL alias, see compiler.py's `col.label(fs.label or ...)`); only
    fall back to position if neither is present, so this never regresses a
    row a caller already keyed positionally on purpose."""
    if ref in data_row:
        return ref
    if label in data_row:
        return label
    return keys[min(ci, len(keys) - 1)] if keys else ref
