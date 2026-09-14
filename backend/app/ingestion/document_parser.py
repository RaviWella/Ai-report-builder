"""Parse an uploaded report SAMPLE (Excel / PDF / image / Word) into header metadata.

Like the Excel parser, this reads only the LAYOUT (column headings + inferred
type) — never the data. PDFs are read with pdfplumber and images with Tesseract
OCR, both LOCALLY, so nothing but the headings ever reaches the AI (privacy,
FR-A2 §8.2). Everything funnels into the same ParsedExcel shape the AI mapping
already consumes.
"""
from __future__ import annotations

import io
import re

from app.ai.base import ExcelColumnMeta
from app.ingestion.excel_parser import ParsedExcel, parse_csv_headers, parse_excel_headers
from app.ingestion.word_doc import extract_doc_lines, is_legacy_word

_IMAGE_EXT = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tif", ".tiff")
_NUM_RE = re.compile(r"^[\s]*[-+]?[\d.,]+\s*%?\s*$")
_MERGEFIELD = re.compile(r"MERGEFIELD\s+\"?([A-Za-z0-9_]+)\"?", re.I)


def _is_docx(filename: str = "", content_type: str = "", content: bytes | None = None) -> bool:
    name = (filename or "").lower()
    ct = (content_type or "").lower()
    if name.endswith(".docx") or "wordprocessingml.document" in ct:
        return True
    # A .docx saved/renamed under a misleading .doc extension still starts with
    # the ZIP signature — trust content over a claimed extension when we have it.
    return bool(content) and content.startswith(b"PK") and (
        name.endswith((".doc", ".dot")) or ct in {"application/msword", "application/x-msword", "application/doc"}
    )


def _is_word(filename: str = "", content_type: str = "", content: bytes | None = None) -> bool:
    return _is_docx(filename, content_type, content) or is_legacy_word(filename, content_type, content)


def parse_document(content: bytes, filename: str = "", content_type: str = "") -> ParsedExcel:
    """Dispatch on file type. Falls back to Excel parsing for unknown types."""
    name = (filename or "").lower()
    ct = (content_type or "").lower()
    if name.endswith(_IMAGE_EXT) or ct.startswith("image/"):
        return _parse_image(content)
    if name.endswith(".pdf") or "pdf" in ct:
        return _parse_pdf(content)
    if _is_word(filename, content_type, content):
        raise ValueError(
            "A Word (.doc/.docx) file isn't in column form — upload it as a sample "
            "letter (Documents) instead of a data/column sample."
        )
    if name.endswith(".csv") or "csv" in ct:
        return parse_csv_headers(content)
    return parse_excel_headers(content, filename=filename, content_type=content_type)


def is_text_document(filename: str = "", content_type: str = "", content: bytes | None = None) -> bool:
    """True for PDFs/images/Word — a sample LETTER we read as flowing text (not columns)."""
    name = (filename or "").lower()
    ct = (content_type or "").lower()
    return (
        name.endswith(_IMAGE_EXT) or ct.startswith("image/")
        or name.endswith(".pdf") or "pdf" in ct
        or _is_word(filename, content_type, content)
    )


def extract_lines(content: bytes, filename: str = "", content_type: str = "") -> list[str]:
    """The document's text as non-empty lines, IN READING ORDER — for turning a
    sample letter (PDF/image/Word) into an editable design. Local only (pdfplumber /
    Tesseract / python-docx / .doc piece table); nothing leaves the server here.
    Excel returns [] (columnar, handled via parse_document instead)."""
    name = (filename or "").lower()
    ct = (content_type or "").lower()
    if name.endswith(_IMAGE_EXT) or ct.startswith("image/"):
        return _image_lines(content)
    if name.endswith(".pdf") or "pdf" in ct:
        return _pdf_lines(content)
    if _is_docx(filename, content_type, content):
        return _docx_lines(content)
    if _is_word(filename, content_type, content):
        return extract_doc_lines(content)
    return []


def _pdf_lines(content: bytes) -> list[str]:
    import pdfplumber

    lines: list[str] = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages[:3]:
            for ln in (page.extract_text() or "").splitlines():
                if ln.strip():
                    lines.append(ln.strip())
    if not lines:
        raise ValueError("No selectable text found in the PDF (is it a scan? try an image)")
    return lines


def _image_lines(content: bytes) -> list[str]:
    try:
        import pytesseract
        from PIL import Image
    except ImportError as exc:  # pragma: no cover
        raise ValueError("Image OCR is not available on this server") from exc

    txt = pytesseract.image_to_string(Image.open(io.BytesIO(content)))
    lines = [ln.strip() for ln in txt.splitlines() if ln.strip()]
    if not lines:
        raise ValueError("No text could be read from the image")
    return lines


def _docx_run_text(paragraph) -> str:
    """Visible paragraph text, with empty MERGEFIELDs shown as «Name» so the
    letter mapper can bind them the same way as a pasted Word template."""
    visible = (paragraph.text or "").replace("\u00a0", " ")
    xml = paragraph._element.xml
    names = _MERGEFIELD.findall(xml)
    if not names:
        return visible.strip()
    out = visible
    seen: set[str] = set()
    for name in names:
        if name in seen:
            continue
        seen.add(name)
        out = f"{out} «{name}»".strip() if out else f"«{name}»"
    return out.strip()


def _docx_table_lines(table) -> list[str]:
    lines: list[str] = []
    for row in table.rows:
        cells = [_docx_run_text(p) for cell in row.cells for p in cell.paragraphs]
        cells = [c for c in cells if c]
        if cells:
            lines.append("  ".join(cells))
    return lines


def _docx_lines(content: bytes) -> list[str]:
    from docx import Document

    try:
        doc = Document(io.BytesIO(content))
    except Exception as exc:
        raise ValueError("Couldn’t read that Word file. Save it as .docx and try again.") from exc

    lines: list[str] = []
    for p in doc.paragraphs:
        t = _docx_run_text(p)
        if t:
            lines.append(t)
    for table in doc.tables:
        lines.extend(_docx_table_lines(table))
    if not lines:
        raise ValueError("No text could be read from that Word file.")
    return lines


# ── shared: a 2D grid of cell strings -> header metadata ───────────────────
def _txt(v: object) -> str:
    if v is None:
        return ""
    s = str(v).strip()
    return "" if s.lower() == "nan" else s


def _grid_to_parsed(grid: list[list[str]]) -> ParsedExcel:
    """Pick the header band (1-2 rows with the most real names) and build columns,
    inferring each column's type from the data cells below it."""
    grid = [[_txt(c) for c in row] for row in grid if any(_txt(c) for c in row)]
    if not grid:
        return ParsedExcel(columns=[], row_count_seen=0)
    width = max(len(r) for r in grid)
    grid = [r + [""] * (width - len(r)) for r in grid]  # pad ragged rows

    def combine(start: int, span: int) -> list[str]:
        out = []
        for j in range(width):
            parts = [grid[start + r][j] for r in range(span) if start + r < len(grid)]
            out.append(" ".join(p for p in parts if p))
        return out

    def multi(i: int) -> bool:  # row i has 2+ filled cells (a real table row)
        return sum(1 for c in grid[i] if c) >= 2

    best = (0, 1, -1)  # start, span, named_count
    for start in range(min(len(grid), 10)):
        named1 = sum(1 for nm in combine(start, 1) if nm)
        if named1 > best[2]:
            best = (start, 1, named1)
        # Use a 2-row header ONLY when both rows are multi-column (a wrapped
        # header) — never a title/total line stacked above the header row.
        if start + 2 <= len(grid) and multi(start) and multi(start + 1):
            named2 = sum(1 for nm in combine(start, 2) if nm)
            if named2 > best[2]:
                best = (start, 2, named2)
    start, span, _ = best
    names = combine(start, span)
    data = grid[start + span :]

    columns: list[ExcelColumnMeta] = []
    for j, name in enumerate(names):
        if not name:
            continue
        col_cells = [row[j] for row in data if j < len(row) and row[j]]
        numeric = bool(col_cells) and all(_NUM_RE.match(c) for c in col_cells)
        columns.append(
            ExcelColumnMeta(
                header=name,
                inferred_type="decimal" if numeric else "string",
                sample_is_empty=not col_cells,
            )
        )
    return ParsedExcel(columns=columns, row_count_seen=len(data))


# ── word-position → grid (robust to borderless tables & mixed alignment) ────
def _split_row(row: list[tuple[float, float, float, str]]) -> list[str]:
    """Split one row's words into cells at gaps MUCH larger than the within-word
    space (a low percentile of gaps is the space baseline)."""
    row = sorted(row, key=lambda w: w[0])
    gaps = [row[i][0] - row[i - 1][1] for i in range(1, len(row))]
    pos = sorted(g for g in gaps if g > 0)
    space = pos[len(pos) // 4] if pos else 0
    thresh = max(space * 3, 15)
    cells, cur = [], [row[0][3]]
    for i in range(1, len(row)):
        if row[i][0] - row[i - 1][1] > thresh:
            cells.append(" ".join(cur)); cur = []
        cur.append(row[i][3])
    cells.append(" ".join(cur))
    return cells


def _words_to_grid(words: list[tuple[float, float, float, str]], row_tol: float = 6.0) -> list[list[str]]:
    """words = (x0, x1, top, text). Cluster into rows by y, then split EACH row
    independently into cells. (Splitting per-row, not anchored to one 'header',
    means a title line collapses to one cell while the real table header keeps its
    columns — so the header-band picker downstream finds the right row.)"""
    if not words:
        return []
    words.sort(key=lambda w: (w[2], w[0]))
    rows: list[list[tuple[float, float, float, str]]] = []
    cur: list = []
    last_top = None
    for w in words:
        if last_top is not None and abs(w[2] - last_top) > row_tol:
            rows.append(cur); cur = []
        cur.append(w); last_top = w[2]
    if cur:
        rows.append(cur)
    return [_split_row(r) for r in rows]


def _parse_pdf(content: bytes) -> ParsedExcel:
    import pdfplumber

    words: list[tuple[float, float, float, str]] = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages[:2]:
            ws = page.extract_words(use_text_flow=False)
            if ws:
                words = [(w["x0"], w["x1"], w["top"], w["text"]) for w in ws]
                break
    if not words:
        raise ValueError("No selectable text found in the PDF (is it a scan? try an image)")
    return _grid_to_parsed(_words_to_grid(words))


def _parse_image(content: bytes) -> ParsedExcel:
    try:
        import pytesseract
        from PIL import Image
    except ImportError as exc:  # pragma: no cover
        raise ValueError("Image OCR is not available on this server") from exc

    img = Image.open(io.BytesIO(content))
    d = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    words = [
        (d["left"][i], d["left"][i] + d["width"][i], d["top"][i], t.strip())
        for i, t in enumerate(d["text"])
        if t.strip() and int(d["conf"][i]) >= 40
    ]
    if not words:
        raise ValueError("No text could be read from the image")
    return _grid_to_parsed(_words_to_grid(words, row_tol=10))
