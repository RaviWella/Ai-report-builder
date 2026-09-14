"""Branded PDF export with WeasyPrint (FR-B11, Architecture §4.6).

Renders an HTML/CSS template (report.html) to PDF. Same presentation_spec drives
column order, formats, conditional highlight and branding. No AI, no datamart.
"""

from __future__ import annotations

import datetime as _dt
from decimal import Decimal
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.domain.enums import FilterOp
from app.domain.report_spec import PresentationSpec
from app.query_engine.runner import QueryResult
from app.rendering.row_key import resolve_row_key

_TEMPLATE_DIR = Path(__file__).parent / "templates"
_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=select_autoescape(["html"]),
)

_OP = {
    FilterOp.GT: lambda a, b: a > b,
    FilterOp.LT: lambda a, b: a < b,
    FilterOp.GTE: lambda a, b: a >= b,
    FilterOp.LTE: lambda a, b: a <= b,
    FilterOp.EQ: lambda a, b: a == b,
    FilterOp.NEQ: lambda a, b: a != b,
}


def render_pdf(
    result: QueryResult, presentation: PresentationSpec, total_labels: set[str] | None = None,
) -> bytes:
    from weasyprint import HTML  # imported lazily (heavy native deps)

    col_refs = [c.ref for c in presentation.columns] or result.columns
    col_meta = {c.ref: c for c in presentation.columns}
    cond_by_ref = {cf.ref: cf for cf in presentation.conditional_formats}

    columns = [
        {
            "label": (col_meta[r].label if r in col_meta and col_meta[r].label
                      else r.split(".", 1)[-1].replace("_", " ").title())
        }
        for r in col_refs
    ]

    # A pivoted report (report_service._apply_pivot) carries each cell's status
    # in a row's `_cell_status: {column_label: status}` — never a real column
    # itself (excluded from col_refs). An arbitrary hex color per status can't
    # be a fixed CSS class like "num"/"hl", so it's an inline style instead.
    status_colors = presentation.pivot.status_colors if presentation.pivot else {}

    rows_out = []
    numeric_cols = set()
    for data_row in result.rows:
        keys = list(data_row.keys())
        # A group subtotal row (report_service._inject_subtotals tags rows
        # "_row_kind": "subtotal") is rendered bold, same idea as the grand-total
        # <tfoot> row below — never itself treated as a highlight/conditional match.
        is_subtotal = data_row.get("_row_kind") == "subtotal"
        cell_status = data_row.get("_cell_status") or {}
        cells = []
        for ci, ref in enumerate(col_refs):
            key = resolve_row_key(data_row, keys, ci, ref, columns[ci]["label"])
            value = data_row.get(key)
            css = []
            if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
                css.append("num")
                numeric_cols.add(ci)
            cf = cond_by_ref.get(ref)
            if not is_subtotal and cf and isinstance(value, (int, float, Decimal)):
                try:
                    if _OP.get(cf.when, lambda a, b: False)(value, cf.value):
                        css.append("hl")
                except TypeError:
                    pass
            style = ""
            status = None if is_subtotal else cell_status.get(ref)
            if status and status in status_colors:
                style = f"background-color: {status_colors[status]};"
            cells.append({"value": _fmt(value, col_meta.get(ref)), "css": " ".join(css), "style": style})
        rows_out.append({"cells": cells, "subtotal": is_subtotal})

    # Per-column totals: classic reports pass friendly headers; rule reports pass
    # output field keys — match either so a renamed heading never drops the total.
    flagged = total_labels or set()
    total_col_indices = [
        ci for ci, ref in enumerate(col_refs)
        if ref in flagged or columns[ci]["label"] in flagged
    ]
    totals = None
    if (total_col_indices or presentation.page.totals) and result.rows:
        totals = []
        for ci, ref in enumerate(col_refs):
            if ci == 0:
                totals.append({"value": "Total", "css": ""})
            elif ci in total_col_indices or (presentation.page.totals and ci in numeric_cols):
                col_sum = _column_sum(result.rows, ci, ref, columns[ci]["label"])
                totals.append({"value": _fmt(col_sum, col_meta.get(ref)), "css": "num"})
            else:
                totals.append({"value": "", "css": ""})

    html = _env.get_template("report.html").render(
        title=presentation.title,
        header=presentation.branding.header,
        footer=presentation.branding.footer,
        logo_url=None,
        orientation="A4 landscape" if presentation.page.orientation == "landscape" else "A4",
        columns=columns,
        rows=rows_out,
        totals=totals,
        provenance=_provenance_line(result),
    )
    return HTML(string=html).write_pdf()


def _provenance_line(result) -> str:  # noqa: ANN001
    """WS-1 — audit-grade lineage stamped on the export footer."""
    parts: list[str] = []
    if result.semantic_version_ref is not None:
        parts.append(f"catalogue v{result.semantic_version_ref}")
    if result.run_id:
        parts.append(f"run {result.run_id[:8]}")
    if result.datamart_snapshot_ref:
        parts.append(f"data {result.datamart_snapshot_ref}")
    if result.result_checksum:
        parts.append(f"checksum {result.result_checksum[:12]}")
    return " · ".join(parts)


def _column_sum(rows: list[dict], ci: int, ref: str, label: str):
    total = 0
    for row in rows:
        if row.get("_row_kind") == "subtotal":
            continue   # a group subtotal is already a sum of its own group — skip it here
        keys = list(row.keys())
        key = resolve_row_key(row, keys, ci, ref, label)
        v = row.get(key)
        if isinstance(v, (int, float, Decimal)) and not isinstance(v, bool):
            total += v
    return total


def _fmt(value, meta) -> str:  # noqa: ANN001
    if value is None:
        return ""
    fmt = meta.format if meta and meta.format else None
    if isinstance(value, _dt.datetime):  # incl. tz-aware (e.g. a timestamptz straight from Postgres)
        naive = value.replace(tzinfo=None) if value.tzinfo else value
        return naive.strftime("%Y-%m-%d %H:%M")
    if isinstance(value, _dt.date):
        return value.isoformat()
    if isinstance(value, _dt.time):     # a bare time column (e.g. a punch time) — HH:MM, no seconds
        return value.strftime("%H:%M")
    if fmt and fmt.startswith("currency") and isinstance(value, (int, float, Decimal)):
        return f"{value:,.2f}"
    if fmt and fmt.startswith("percentage") and isinstance(value, (int, float, Decimal)):
        return f"{value * 100:.2f}%"
    if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
        return f"{value:,}" if isinstance(value, int) else f"{value:,.2f}"
    return str(value)
