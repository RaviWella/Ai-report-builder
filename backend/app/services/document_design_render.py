"""Render a canvas DocumentDesign (letter / email) — bind data per record.

Pipeline:
  1. Wide per-record row via the common Query Engine (reuses refs, joins, guards).
  2. Compose each block to HTML, substituting `{{ref}}` merge tokens and field/table
     bindings with the record's values (values HTML-escaped; builder markup trusted).
  3. Letters -> one page per record, concatenated with page breaks -> PDF (WeasyPrint).
     Emails -> the composed body HTML (+ token-substituted subject) for one record.

Nothing here is HR-specific; every binding is a semantic ref resolved by the caller.
"""

from __future__ import annotations

import calendar
import re
from datetime import datetime
from html import escape
from typing import Any

from app.core.tenancy import TenantContext
from app.domain.document_design import TOKEN_RE, DesignBlock, DocumentDesign, parse_token
from app.domain.enums import FilterOp
from app.domain.report_spec import DataSpec, FieldSelection, FilterClause
from app.domain.semantic import SemanticCatalog
from app.query_engine.runner import run_query
from app.rendering.document_renderer import fmt_amount, render_html_pdf, render_records_docx
from app.services.letter_html import sanitize_letter_html

_PAGE_MM = {"A4": (210, 297), "Letter": (216, 279)}


def _fmt(value: Any) -> str:
    """A merge value as display text: numbers grouped, everything else as-is."""
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        return fmt_amount(value)
    return str(value)


def substitute_tokens(html: str | None, row: dict[str, Any]) -> str:
    """Replace every `{{ref}}` (or `{{ref|value=text|...}}`) in trusted builder
    markup with the record's value (HTML-escaped; the surrounding markup is not).
    Each occurrence is resolved independently, so the same ref can carry a
    DIFFERENT value map at different spots (e.g. he/she in one place, him/her
    in another, both driven by the one employee.gender field)."""
    if not html:
        return ""
    out = sanitize_letter_html(html)

    def repl(m: re.Match[str]) -> str:
        parsed = parse_token(m.group(1))
        if parsed is None:
            return m.group(0)  # not actually ref-shaped — leave untouched
        ref, value_map = parsed
        raw = _fmt(row.get(ref))
        text = value_map.get(raw, value_map.get("default", raw)) if value_map else raw
        return escape(text)

    return TOKEN_RE.sub(repl, out)


def _style_attr(block: DesignBlock) -> str:
    css: list[str] = []
    if block.align:
        css.append(f"text-align:{block.align}")
    style = block.style or {}
    mapping = {
        "fontSize": "font-size", "color": "color", "fontWeight": "font-weight",
        "fontStyle": "font-style", "lineHeight": "line-height", "marginTop": "margin-top",
        "marginBottom": "margin-bottom", "background": "background", "fontFamily": "font-family",
    }
    for key, cssname in mapping.items():
        val = style.get(key)
        if val is not None and val != "":
            css.append(f"{cssname}:{escape(str(val))}")
    return ";".join(css)


def _block_html(block: DesignBlock, row: dict[str, Any], detail_rows: list[list[dict]]) -> str:
    style = _style_attr(block)
    wrap = f' style="{style}"' if style else ""
    t = block.type
    if t == "text":
        return f'<div class="blk"{wrap}>{substitute_tokens(block.html, row)}</div>'
    if t == "field":
        val = _fmt(row.get(block.ref))
        body = f"{escape(block.prefix or '')}{escape(val)}{escape(block.suffix or '')}"
        lbl = f'<span class="fld-label">{escape(block.label)}</span> ' if block.label else ""
        return f'<div class="blk"{wrap}>{lbl}{body}</div>'
    if t == "image":
        if not block.src:
            return ""
        w = f"width:{block.width_pct}%" if block.width_pct else "max-width:200px"
        return f'<div class="blk"{wrap}><img src="{escape(block.src)}" style="{w}"/></div>'
    if t == "divider":
        return '<hr class="blk-divider"/>'
    if t == "spacer":
        h = block.height_px or 16
        return f'<div style="height:{int(h)}px"></div>'
    if t == "signature":
        lbl = escape(block.label or "Signature")
        return f'<div class="blk sig"{wrap}><div class="sig-line"></div><div class="sig-label">{lbl}</div></div>'
    if t == "table":
        cols = block.columns or []
        head = "".join(f"<th>{escape(c.label or c.ref)}</th>" for c in cols)
        # data-bound rows: detail provider rows, else the record's own single row.
        src_rows = detail_rows if block.provider else [
            [{"ref": c.ref, "value": row.get(c.ref)} for c in cols]
        ]
        body_rows = ""
        if block.provider:
            # provider rows are list[list[{label,value}]]; render values in column order
            for item in detail_rows:
                by_label = {d.get("label"): d.get("value") for d in item}
                tds = "".join(
                    f"<td>{escape(_fmt(by_label.get(c.label or c.ref)))}</td>" for c in cols
                )
                body_rows += f"<tr>{tds}</tr>"
        else:
            tds = "".join(f"<td>{escape(_fmt(row.get(c.ref)))}</td>" for c in cols)
            body_rows = f"<tr>{tds}</tr>"
        return (
            f'<table class="blk-table"{wrap}><thead><tr>{head}</tr></thead>'
            f"<tbody>{body_rows}</tbody></table>"
        )
    return ""


_BASE_CSS = """
* { box-sizing: border-box; }
/* Latin first, then Noto for Tamil/Sinhala glyph coverage (per-glyph fallback). */
body { font-family: 'Helvetica Neue', Arial, 'Noto Sans Tamil', 'Noto Sans Sinhala', 'Noto Sans', sans-serif; color:#1F2937; font-size:12pt; }
.page { page-break-after: always; }
.page:last-child { page-break-after: auto; }
.blk { margin: 4px 0; }
.blk-divider { border:0; border-top:1px solid #D1D5DB; margin:12px 0; }
.fld-label { color:#6B7280; font-weight:600; }
.sig-line { border-top:1px solid #374151; width:220px; margin-top:36px; }
.sig-label { color:#6B7280; font-size:10pt; margin-top:2px; }
.blk-table { border-collapse: collapse; width:100%; margin:8px 0; font-size:11pt; }
.blk-table th, .blk-table td { border:1px solid #E5E7EB; padding:4px 8px; text-align:left; }
.blk-table th { background:#F3F4F6; }
img { display:inline-block; }
.doc-header { border-bottom:1px solid #E5E7EB; padding-bottom:8px; margin-bottom:14px; }
.doc-footer { border-top:1px solid #E5E7EB; padding-top:8px; margin-top:18px; color:#6B7280; font-size:10pt; }
/* rich-text blocks: images, tables and dividers added inside the editor */
.blk img { max-width:100%; height:auto; }
.blk table { border-collapse:collapse; width:100%; margin:8px 0; }
.blk td, .blk th { border:1px solid #D1D5DB; padding:4px 8px; }
.blk th { background:#F3F4F6; font-weight:600; }
.blk hr { border:none; border-top:1px solid #D1D5DB; margin:10px 0; }
"""


def _page_css(design: DocumentDesign) -> str:
    w, h = _PAGE_MM.get(design.page_size, _PAGE_MM["A4"])
    if design.orientation == "landscape":
        w, h = h, w
    page_num = ""
    if design.show_page_numbers:
        page_num = ('@bottom-right { content: "Page " counter(page) " of " counter(pages); '
                    'font-size: 9pt; color: #6B7280; }')
    t, r, b, left = design.margins()
    return f"@page {{ size: {w}mm {h}mm; margin: {t}mm {r}mm {b}mm {left}mm; {page_num} }}"


def compose_record_html(
    design: DocumentDesign, row: dict[str, Any],
    detail_by_provider: dict[str, list[list[dict]]] | None = None,
) -> str:
    """The inner HTML for ONE record (no <html>/<head> wrapper)."""
    detail_by_provider = detail_by_provider or {}
    parts: list[str] = []
    if design.header_html:
        parts.append(f'<div class="doc-header">{substitute_tokens(design.header_html, row)}</div>')
    parts += [
        _block_html(b, row, detail_by_provider.get(b.provider or "", []))
        for b in design.blocks
    ]
    if design.footer_html:
        parts.append(f'<div class="doc-footer">{substitute_tokens(design.footer_html, row)}</div>')
    return "".join(parts)


def _document_html(design: DocumentDesign, records_html: list[str]) -> str:
    pages = "".join(f'<div class="page">{h}</div>' for h in records_html)
    return (
        f"<!doctype html><html><head><meta charset='utf-8'><style>"
        f"{_page_css(design)}{_BASE_CSS}</style></head><body>{pages}</body></html>"
    )


def _fetch_rows(
    ctx: TenantContext, datamart_key: str, catalog: SemanticCatalog, design: DocumentDesign,
    *, year: int | None, month: int | None, record_key: str | None, max_records: int | None,
) -> list[dict[str, Any]]:
    filters: list[FilterClause] = []
    if design.period_year_ref and design.period_month_ref and year and month:
        filters.append(FilterClause(ref=design.period_year_ref, op=FilterOp.EQ, value=year))
        filters.append(FilterClause(ref=design.period_month_ref, op=FilterOp.EQ, value=month))
    if design.record_key_ref and record_key:
        filters.append(FilterClause(ref=design.record_key_ref, op=FilterOp.EQ, value=record_key))
    refs = design.value_refs()
    if not refs:
        return [{}]  # a static letter with no bindings still renders one page
    data_spec = DataSpec(
        entity="employee",
        fields=[FieldSelection(ref=r, label=r) for r in refs],
        filters=filters,
    )
    result = run_query(
        ctx=ctx, datamart_key=datamart_key, spec=data_spec, catalog=catalog,
        params={}, row_limit=100_000,
    )
    rows = result.rows
    return rows[:max_records] if max_records else rows


def _system_values() -> dict[str, str]:
    """Built-in tokens resolved at generation time — e.g. today's date on a letter."""
    now = datetime.now()
    return {
        "system.date": now.strftime("%d %B %Y"),   # 08 July 2026
        "system.date_iso": now.strftime("%Y-%m-%d"),
        "system.year": str(now.year),
        "system.month": now.strftime("%B"),
        "system.day": now.strftime("%d"),
    }


def _with_manual(row: dict[str, Any], manual: dict[str, str] | None) -> dict[str, Any]:
    """Row augmented with the built-in system tokens + issuer-typed `manual.<key>` values."""
    out: dict[str, Any] = {**row, **_system_values()}
    if manual:
        out.update({f"manual.{k}": v for k, v in manual.items()})
    return out


def generate_letters(
    ctx: TenantContext, datamart_key: str, catalog: SemanticCatalog, design: DocumentDesign,
    *, year: int | None = None, month: int | None = None,
    record_key: str | None = None, max_records: int | None = None,
    manual: dict[str, str] | None = None,
) -> bytes:
    """One page per matching record -> a single multi-page PDF."""
    rows = _fetch_rows(
        ctx, datamart_key, catalog, design,
        year=year, month=month, record_key=record_key, max_records=max_records,
    )
    records_html = [compose_record_html(design, _with_manual(row, manual)) for row in (rows or [{}])]
    return render_html_pdf(_document_html(design, records_html))


def generate_letters_docx(
    ctx: TenantContext, datamart_key: str, catalog: SemanticCatalog, design: DocumentDesign,
    *, year: int | None = None, month: int | None = None,
    record_key: str | None = None, max_records: int | None = None,
    manual: dict[str, str] | None = None,
) -> bytes:
    """Same records as generate_letters, but an EDITABLE Word (.docx) instead of a PDF."""
    rows = _fetch_rows(
        ctx, datamart_key, catalog, design,
        year=year, month=month, record_key=record_key, max_records=max_records,
    )
    records_html = [compose_record_html(design, _with_manual(row, manual)) for row in (rows or [{}])]
    return render_records_docx(records_html)


def compose_labelled(design: DocumentDesign, label_of) -> str:
    """Render the design with each `{{ref}}` shown as a bracketed field LABEL —
    a data-free preview of the layout (AC-TC-05). `label_of(ref) -> str`."""
    def sub(html: str | None) -> str:
        if not html:
            return ""
        out = sanitize_letter_html(html)

        def repl(m: re.Match[str]) -> str:
            parsed = parse_token(m.group(1))
            if parsed is None:
                return m.group(0)
            return f"[{escape(label_of(parsed[0]))}]"

        return TOKEN_RE.sub(repl, out)

    parts: list[str] = []
    if design.header_html:
        parts.append(f'<div class="doc-header">{sub(design.header_html)}</div>')
    for b in design.blocks:
        if b.type == "text":
            parts.append(f'<div class="blk">{sub(b.html)}</div>')
        elif b.type == "field":
            parts.append(f'<div class="blk">{escape((b.label + ": ") if b.label else "")}[{escape(label_of(b.ref) if b.ref else "field")}]</div>')
        elif b.type == "signature":
            parts.append(f'<div class="blk sig"><div class="sig-line"></div><div class="sig-label">{escape(b.label or "Signature")}</div></div>')
        elif b.type == "divider":
            parts.append('<hr class="blk-divider"/>')
    if design.footer_html:
        parts.append(f'<div class="doc-footer">{sub(design.footer_html)}</div>')
    body = "".join(parts)
    return (
        f"<!doctype html><html><head><meta charset='utf-8'><style>"
        f"{_page_css(design)}{_BASE_CSS}</style></head><body>"
        f'<div class="page">{body}</div></body></html>'
    )


def preview_email(
    ctx: TenantContext, datamart_key: str, catalog: SemanticCatalog, design: DocumentDesign,
    *, subject: str, year: int | None = None, month: int | None = None,
    record_key: str | None = None, manual: dict[str, str] | None = None,
) -> dict:
    """Compose the email body + subject for ONE record (the first match) for preview."""
    rows = _fetch_rows(
        ctx, datamart_key, catalog, design,
        year=year, month=month, record_key=record_key, max_records=1,
    )
    row = _with_manual(rows[0] if rows else {}, manual)
    body = (
        f"<!doctype html><html><head><meta charset='utf-8'><style>{_BASE_CSS}</style>"
        f"</head><body>{compose_record_html(design, row)}</body></html>"
    )
    return {
        "subject": substitute_tokens(subject, row),
        "html": body,
        "record_count": len(rows),
    }


def preview_letter_html(
    ctx: TenantContext, datamart_key: str, catalog: SemanticCatalog, design: DocumentDesign,
    *, year: int | None = None, month: int | None = None, record_key: str | None = None,
    manual: dict[str, str] | None = None,
) -> dict:
    """The composed HTML for the first matching record — an in-browser letter preview."""
    rows = _fetch_rows(
        ctx, datamart_key, catalog, design,
        year=year, month=month, record_key=record_key, max_records=1,
    )
    row = _with_manual(rows[0] if rows else {}, manual)
    period = f"{calendar.month_name[month]} {year}" if year and month else None
    body = (
        f"<!doctype html><html><head><meta charset='utf-8'><style>"
        f"{_page_css(design)}{_BASE_CSS}</style></head><body>"
        f'<div class="page">{compose_record_html(design, row)}</div></body></html>'
    )
    return {"html": body, "record_count": len(rows), "period": period}
