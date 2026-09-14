"""Per-record document PDF (one page per record) — renders document.html, which
loops records with a page break between each, to one multi-page PDF via WeasyPrint.
Generic: it lays out whatever sections/lines/detail-blocks the document service
resolved, with no domain-specific knowledge.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

_TEMPLATE_DIR = Path(__file__).parent / "templates"
_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=select_autoescape(["html"]),
)


def fmt_amount(value: object) -> str:
    if value is None or value == "":
        return ""
    try:
        return f"{Decimal(str(value)):,.2f}"
    except (InvalidOperation, ValueError):
        return str(value)


def render_document_pdf(context: dict) -> bytes:
    from weasyprint import HTML  # heavy native deps — import lazily

    html = _env.get_template("document.html").render(**context)
    return HTML(string=html).write_pdf()


def render_html_pdf(html: str) -> bytes:
    """Render a fully-formed HTML string (a composed canvas design) to a PDF."""
    from weasyprint import HTML  # heavy native deps — import lazily

    return HTML(string=html).write_pdf()


def render_records_docx(records_html: list[str]) -> bytes:
    """Build an EDITABLE Word (.docx) from per-record HTML fragments — one record
    per page (page break between). Formatting, tables, images and Unicode (incl.
    Tamil/Sinhala) are carried over so HR can tweak the letter in Word."""
    import io

    from docx import Document  # optional deps — import lazily
    from htmldocx import HtmlToDocx

    doc = Document()
    parser = HtmlToDocx()
    for i, html in enumerate(records_html or ["<p></p>"]):
        if i:
            doc.add_page_break()
        parser.add_html_to_document(html, doc)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
