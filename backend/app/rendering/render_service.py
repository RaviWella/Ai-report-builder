"""Rendering facade — picks the renderer for the requested export format."""

from __future__ import annotations

from app.domain.enums import ExportFormat
from app.domain.report_spec import PresentationSpec
from app.query_engine.runner import QueryResult
from app.rendering.excel_renderer import render_excel
from app.rendering.pdf_renderer import render_pdf

_MIME = {
    ExportFormat.XLSX: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ExportFormat.PDF: "application/pdf",
}


def render(
    result: QueryResult, presentation: PresentationSpec, fmt: ExportFormat,
    total_labels: set[str] | None = None,
) -> tuple[bytes, str]:
    """Return (bytes, mime_type) for the export. `total_labels` are the column
    headers the user flagged to show a SUM for in the totals row."""
    if fmt == ExportFormat.XLSX:
        return render_excel(result, presentation, total_labels), _MIME[fmt]
    if fmt == ExportFormat.PDF:
        return render_pdf(result, presentation, total_labels), _MIME[fmt]
    raise ValueError(f"Unsupported export format: {fmt!r}")
