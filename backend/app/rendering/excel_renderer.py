"""Branded Excel export with XlsxWriter (FR-B11, Architecture §4.6).

Applies the presentation_spec: column order/labels/widths/formats, conditional
formats, header/footer/logo and totals. Operates purely on already-fetched rows;
it never touches the AI or the datamart.
"""

from __future__ import annotations

import datetime as _dt
import io
import re
from decimal import Decimal

import xlsxwriter

from app.domain.enums import FilterOp
from app.domain.report_spec import ColumnPresentation, PresentationSpec
from app.query_engine.runner import QueryResult
from app.rendering.row_key import resolve_row_key

_FORMAT_SPECS = {
    "currency": {"num_format": "#,##0.00"},
    "percentage": {"num_format": "0.00%"},
    "date": {"num_format": "yyyy-mm-dd"},
    "datetime": {"num_format": "yyyy-mm-dd hh:mm:ss"},
    "time": {"num_format": "hh:mm"},
    "number": {"num_format": "#,##0"},
}

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ISO_TIME = re.compile(r"^\d{2}:\d{2}(:\d{2})?$")
_CELL_BORDER = {"border": 1, "border_color": "#E5E7EB"}


def render_excel(
    result: QueryResult, presentation: PresentationSpec, total_labels: set[str] | None = None
) -> bytes:
    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True})
    ws = wb.add_worksheet((presentation.title or "Report")[:31])
    # Hide the default cell gridlines so empty areas (title/branding) are clean;
    # the data table keeps its own explicit borders.
    ws.hide_gridlines(2)

    title_fmt = wb.add_format({"bold": True, "font_size": 15, "font_color": "#111827"})
    sub_fmt = wb.add_format({"font_color": "#6B7280", "font_size": 10})
    header_fmt = wb.add_format(
        {"bold": True, "bg_color": "#F3F4F6", "font_color": "#111827", "border": 1,
         "align": "left", "valign": "vcenter"}
    )
    footer_fmt = wb.add_format({"italic": True, "font_color": "#9CA3AF", "font_size": 9})

    # Columns: presentation order if set, else the query result columns (labels).
    using_result_cols = not presentation.columns
    col_refs = [c.ref for c in presentation.columns] or result.columns
    col_meta = {c.ref: c for c in presentation.columns}

    def header_label(ci: int, ref: str) -> str:
        if using_result_cols:
            return str(result.columns[ci])
        meta = col_meta.get(ref)
        return meta.label if meta and meta.label else ref.split(".", 1)[-1].replace("_", " ").title()

    ncols = max(len(col_refs), 1)

    def write_banner(r: int, text: str, fmt) -> None:  # noqa: ANN001
        # Span the whole width as ONE merged cell so the title area has no internal
        # column grid / borders (just the text, clean).
        if ncols > 1:
            ws.merge_range(r, 0, r, ncols - 1, text, fmt)
        else:
            ws.write(r, 0, text, fmt)

    row = 0
    if presentation.branding.header:
        write_banner(row, presentation.branding.header, sub_fmt)
        row += 1
    write_banner(row, presentation.title or "Report", title_fmt)
    row += 2
    header_row = row

    # Track the natural width of each column from its header + values.
    widths = [len(header_label(ci, r)) for ci, r in enumerate(col_refs)]

    cell_formats: dict[str, object] = {}
    # A group subtotal row (report_service._inject_subtotals tags rows
    # "_row_kind": "subtotal") is bold/shaded, but keeps each column's OWN number
    # format (date/currency/etc) layered on top — losing it would show a raw
    # Excel date serial instead of a date on the Total row.
    subtotal_formats: dict[str, object] = {}
    plain = wb.add_format(_CELL_BORDER)
    subtotal_plain = wb.add_format({**_CELL_BORDER, "bold": True, "bg_color": "#F3F4F6"})
    for ci, ref in enumerate(col_refs):
        ws.write(header_row, ci, header_label(ci, ref), header_fmt)
        meta = col_meta.get(ref)
        fmt_dict = _column_format_dict(meta, ref, ci, result.rows, header_label(ci, ref))
        cell_formats[ref] = wb.add_format(fmt_dict)
        subtotal_formats[ref] = wb.add_format({**fmt_dict, "bold": True, "bg_color": "#F3F4F6"})

    # A pivoted report (report_service._apply_pivot) carries each cell's status
    # in a row's `_cell_status: {column_label: status}` — never a real column
    # itself (excluded from col_refs). One extra format per (column, status)
    # actually used, built on demand: the column's own base format (so a
    # numeric pivot value still gets its number formatting) with the status's
    # color layered on top, same layering subtotal_formats already does.
    status_colors = presentation.pivot.status_colors if presentation.pivot else {}
    status_formats: dict[tuple[str, str], object] = {}

    def status_format(ci: int, ref: str, status: str):
        key = (ref, status)
        if key not in status_formats:
            base = _column_format_dict(col_meta.get(ref), ref, ci, result.rows, header_label(ci, ref))
            status_formats[key] = wb.add_format({**base, "bg_color": status_colors[status]})
        return status_formats[key]

    data_start = header_row + 1
    for ri, data_row in enumerate(result.rows):
        keys = list(data_row.keys())
        is_subtotal = data_row.get("_row_kind") == "subtotal"
        cell_status = data_row.get("_cell_status") or {}
        for ci, ref in enumerate(col_refs):
            key = resolve_row_key(data_row, keys, ci, ref, header_label(ci, ref))
            value = data_row.get(key)
            status = cell_status.get(ref)
            if is_subtotal:
                fmt = subtotal_formats.get(ref, subtotal_plain)
            elif status and status in status_colors:
                fmt = status_format(ci, ref, status)
            else:
                fmt = cell_formats.get(ref, plain)
            # Excel has no timezone concept — xlsxwriter raises on a tz-aware
            # datetime (e.g. a `timestamptz` column straight from Postgres).
            if isinstance(value, _dt.datetime) and value.tzinfo is not None:
                value = value.replace(tzinfo=None)
            ws.write(data_start + ri, ci, value, fmt)
            if value is not None:
                widths[ci] = max(widths[ci], len(_display_value(value)))

    # Auto-fit each column (clamped to a readable range).
    for ci, w in enumerate(widths):
        ws.set_column(ci, ci, min(max(w + 3, 12), 55))

    # Keep headers visible while scrolling.
    ws.freeze_panes(data_start, 0)
    ws.set_row(header_row, 22)

    # Totals row. Per-column when specific columns are flagged (total_labels).
    # Classic reports pass friendly column headers; rule reports pass output field
    # keys — match either so renaming a heading never breaks the totals row.
    # Otherwise the page-level "totals" toggle sums every column (backward-
    # compatible grand total). NOTE: this SUMs the raw cell range, so a report
    # combining this grand-total toggle WITH group subtotal rows
    # (report_service._inject_subtotals) would double-count — no report does both
    # today, but a live SUM formula can't cleanly skip interspersed rows if one
    # ever does.
    labels = total_labels or set()
    total_cols = [
        ci for ci, ref in enumerate(col_refs)
        if ref in labels or header_label(ci, ref) in labels
    ]
    if (total_cols or presentation.page.totals) and result.rows:
        total_row = data_start + len(result.rows)
        total_fmt = wb.add_format({"bold": True, "top": 2, "border_color": "#1F2937"})
        ws.write(total_row, 0, "Total", total_fmt)
        cols_to_sum = total_cols or list(range(1, len(col_refs)))
        for ci in cols_to_sum:
            if ci == 0:
                continue
            col_letter = xlsxwriter.utility.xl_col_to_name(ci)
            ws.write_formula(
                total_row, ci,
                f"=SUM({col_letter}{data_start + 1}:{col_letter}{total_row})", total_fmt,
            )

    if presentation.branding.footer:
        ws.write(data_start + len(result.rows) + 2, 0, presentation.branding.footer, footer_fmt)

    _apply_conditional_formats(wb, ws, presentation, col_refs, data_start, len(result.rows))

    wb.close()
    return buf.getvalue()


def _display_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, _dt.datetime):
        dt = value.replace(tzinfo=None) if value.tzinfo else value
        return dt.isoformat(sep=" ", timespec="seconds")
    if isinstance(value, _dt.date):
        return value.isoformat()
    return str(value)


def _infer_format_key(value: object) -> str | None:
    if isinstance(value, _dt.datetime):
        return "datetime"
    if isinstance(value, _dt.date):
        return "date"
    if isinstance(value, _dt.time):     # a bare time column (e.g. a punch time) — not a date/datetime
        return "time"
    if isinstance(value, str) and _ISO_DATE.match(value):
        return "date"
    if isinstance(value, str) and _ISO_TIME.match(value):
        return "time"
    return None


def _column_format_dict(
    meta: ColumnPresentation | None,
    ref: str,
    ci: int,
    rows: list[dict],
    label: str,
) -> dict:
    """The Excel number-format properties for a column — explicit presentation
    first, then infer from the first non-null value (dates must not export as
    serials). Returns a plain dict (not a built xlsxwriter Format) so a caller
    can layer extra properties on top, e.g. bold+shaded for a subtotal row,
    without losing the column's own date/currency formatting."""
    if meta and meta.format:
        base = meta.format.split(":", 1)[0]
        if base in _FORMAT_SPECS:
            return {**_FORMAT_SPECS[base], **_CELL_BORDER}

    for data_row in rows:
        keys = list(data_row.keys())
        key = resolve_row_key(data_row, keys, ci, ref, label)
        value = data_row.get(key)
        if value is None:
            continue
        fmt_key = _infer_format_key(value)
        if fmt_key:
            return {**_FORMAT_SPECS[fmt_key], **_CELL_BORDER}
        break
    return dict(_CELL_BORDER)


def _apply_conditional_formats(wb, ws, presentation, col_refs, data_start, n_rows):  # noqa: ANN001
    if not n_rows:
        return
    op_map = {
        FilterOp.GT: ">", FilterOp.LT: "<", FilterOp.GTE: ">=",
        FilterOp.LTE: "<=", FilterOp.EQ: "==", FilterOp.NEQ: "!=",
    }
    style = wb.add_format({"bg_color": "#FEF3C7"})
    for cf in presentation.conditional_formats:
        if cf.ref not in col_refs or cf.when not in op_map:
            continue
        ci = col_refs.index(cf.ref)
        ws.conditional_format(
            data_start, ci, data_start + n_rows - 1, ci,
            {"type": "cell", "criteria": op_map[cf.when], "value": cf.value, "format": style},
        )
