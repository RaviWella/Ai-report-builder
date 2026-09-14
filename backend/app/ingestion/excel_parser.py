"""Excel ingestion — headers + local type inference, ROWS STRIPPED (FR-A2, §8.2).

The single most important privacy safeguard: an uploaded sample sheet may contain
real data, so this module reads it, infers column types LOCALLY with pandas, and
returns ONLY the header names + inferred types. The actual data rows never leave
this function and are NEVER passed to the AI Adapter.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass

import pandas as pd

from app.ai.base import ExcelColumnMeta
from app.ingestion.word_doc import is_legacy_word

# pandas dtype kind -> our semantic FieldType string
_DTYPE_MAP = {
    "i": "integer",
    "u": "integer",
    "f": "decimal",
    "b": "boolean",
    "M": "datetime",
    "O": "string",
}


@dataclass
class ParsedExcel:
    columns: list[ExcelColumnMeta]
    row_count_seen: int  # how many rows existed (for the UI only — NOT sent to AI)


def _cell_text(v) -> str:  # noqa: ANN001
    """A trimmed string for a cell, or '' for blanks/NaN/numbers-as-header noise."""
    if v is None:
        return ""
    if isinstance(v, float) and pd.isna(v):
        return ""
    s = str(v).strip()
    return "" if s.lower() == "nan" else s


def _combine_header(raw: pd.DataFrame, start: int, span: int) -> list[str]:
    """Build per-column names by joining the header cells across `span` rows
    (handles 2-row / merged-section paysheet headers). Merged cells appear only in
    their anchor column (pandas leaves the rest NaN), so joining recovers every
    sub-column name."""
    names: list[str] = []
    for j in range(raw.shape[1]):
        parts = [_cell_text(raw.iat[r, j]) for r in range(start, start + span)]
        names.append(" ".join(p for p in parts if p))
    return names


def _parse_tabular(raw: pd.DataFrame) -> ParsedExcel:
    """Shared header-band detection + type inference for any tabular upload."""
    n_rows = raw.shape[0]

    def filled_cells(row: int) -> int:
        return sum(1 for j in range(raw.shape[1]) if _cell_text(raw.iat[row, j]))

    # Search the first rows for the header BAND (1 or 2 rows) with the most names.
    best = (0, 1, -1)  # (start, span, named_count)
    for start in range(min(n_rows, 12)):
        for span in (1, 2):
            if start + span > n_rows:
                continue
            # 2-row headers only when BOTH rows are multi-column (not a title line
            # stacked above the real header — common in HR CSV/Excel exports).
            if span == 2 and (filled_cells(start) < 2 or filled_cells(start + 1) < 2):
                continue
            named = sum(1 for nm in _combine_header(raw, start, span) if nm)
            # Prefer a 2-row band only if it adds real names over the 1-row band.
            if named > best[2]:
                best = (start, span, named)
    start, span, _ = best

    names = _combine_header(raw, start, span)
    data = raw.iloc[start + span :].reset_index(drop=True)

    columns: list[ExcelColumnMeta] = []
    for j, name in enumerate(names):
        if not name:  # blank header cell -> not a real reporting column
            continue
        series = data.iloc[:, j]
        columns.append(
            ExcelColumnMeta(
                header=name,
                inferred_type=_infer_type(series),  # local only (§8.2b)
                sample_is_empty=bool(series.dropna().empty),
            )
        )
    row_count = int(len(data))
    del raw, data  # drop so no row data lingers
    return ParsedExcel(columns=columns, row_count_seen=row_count)


def _excel_engine(filename: str = "", content_type: str = "") -> str | None:
    """Pick the pandas engine for legacy/binary Excel formats."""
    name = (filename or "").lower()
    if name.endswith(".xlsb"):
        return "pyxlsb"
    if name.endswith((".xlsx", ".xlsm")):
        return "openpyxl"
    if name.endswith(".xls"):
        return "xlrd"
    ct = (content_type or "").lower()
    if "spreadsheetml.sheet.binary" in ct:
        return "pyxlsb"
    if ct == "application/vnd.ms-excel":
        return "xlrd"
    return None


def _looks_like_html(content: bytes) -> bool:
    """Many HR systems export HTML tables with a .xls extension."""
    head = content[:4096].lstrip().lower()
    return (
        head.startswith(b"<!")
        or head.startswith(b"<html")
        or b"<table" in head
        or b"<meta" in head
    )


def _read_html_table(content: bytes) -> pd.DataFrame:
    """Parse an HTML spreadsheet export into a headerless DataFrame."""
    tables = pd.read_html(io.BytesIO(content), header=None)
    if not tables:
        raise ValueError("No table found in this HTML spreadsheet export.")
    # HR exports usually have one main table — pick the widest.
    return max(tables, key=lambda t: t.shape[1])


def _read_excel_bytes(
    content: bytes,
    sheet: str | int = 0,
    *,
    filename: str = "",
    content_type: str = "",
) -> pd.DataFrame:
    """Read Excel bytes with engine fallbacks for legacy/binary/HTML exports."""
    if _looks_like_html(content):
        return _read_html_table(content)

    if is_legacy_word(filename, content_type, content):
        raise ValueError(
            "This is a Word document, not a spreadsheet. On Letters, use Start from a sample."
        )

    name = (filename or "").lower()
    attempts: list[tuple[str, dict]] = []
    primary = _excel_engine(filename, content_type)
    if primary:
        attempts.append((primary, {"engine": primary}))
    if name.endswith(".xls"):
        for eng in ("xlrd", "openpyxl"):
            if not any(k.get("engine") == eng for _, k in attempts):
                attempts.append((eng, {"engine": eng}))
    if name.endswith(".xlsb") and not any(k.get("engine") == "pyxlsb" for _, k in attempts):
        attempts.append(("pyxlsb", {"engine": "pyxlsb"}))
    if not attempts:
        attempts.append(("auto", {}))

    errors: list[str] = []
    for label, eng_kw in attempts:
        try:
            return pd.read_excel(io.BytesIO(content), sheet_name=sheet, header=None, **eng_kw)
        except ImportError as exc:
            errors.append(f"{label}: missing library ({exc})")
        except Exception as exc:
            errors.append(f"{label}: {exc}")

    # Some .xls files are HTML without a doctype — try table parse as last resort.
    try:
        return _read_html_table(content)
    except Exception as exc:
        errors.append(f"html: {exc}")

    hint = ""
    if name.endswith(".xls"):
        hint = " Try opening it in Excel and Save As .xlsx or .csv."
    detail = errors[0] if errors else "unknown error"
    raise ValueError(f"Could not read this spreadsheet.{hint} ({detail})")


def _decode_text(content: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return content.decode(enc)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="replace")


def _detect_csv_delimiter(lines: list[str]) -> str:
    """Pick the delimiter used on the widest early row (handles HR title rows)."""
    sample = lines[:20]
    best_sep, best_count = ",", 0
    for sep in (",", ";", "\t", "|"):
        counts = [ln.count(sep) for ln in sample if ln.strip()]
        if counts and max(counts) > best_count:
            best_sep, best_count = sep, max(counts)
    return best_sep


def _read_csv_ragged(content: bytes) -> pd.DataFrame:
    """Read CSV/TSV even when a title row has fewer columns than the header."""
    text = _decode_text(content)
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        raise ValueError("Empty CSV file.")

    sep = _detect_csv_delimiter(lines)
    rows: list[list[str]] = []
    for ln in lines:
        try:
            row = next(csv.reader([ln], delimiter=sep))
        except csv.Error:
            row = [ln]
        rows.append([c.strip() for c in row])

    width = max(len(r) for r in rows)
    padded = [r + [""] * (width - len(r)) for r in rows]
    return pd.DataFrame(padded)


def _read_csv_bytes(content: bytes) -> pd.DataFrame:
    """Read CSV with delimiter sniffing and fallbacks for messy HR exports."""
    if _looks_like_html(content):
        return _read_html_table(content)

    # HR CSV exports often have a 1-cell title row then a wide header row — the
    # ragged reader handles that; pandas' C engine fails on it outright.
    errors: list[str] = []
    try:
        raw = _read_csv_ragged(content)
        if raw.shape[1] >= 2:
            return raw
    except Exception as exc:
        errors.append(str(exc))

    text = _decode_text(content)
    for kwargs in (
        {"sep": None, "engine": "python"},
        {"sep": ",", "engine": "python", "on_bad_lines": "skip"},
        {"sep": ";", "engine": "python", "on_bad_lines": "skip"},
        {"sep": "\t", "engine": "python", "on_bad_lines": "skip"},
    ):
        try:
            raw = pd.read_csv(io.StringIO(text), header=None, **kwargs)
            if raw.shape[1] >= 2:
                return raw
        except Exception as exc:
            errors.append(str(exc))

    detail = errors[0] if errors else "unknown error"
    raise ValueError(f"Could not read this CSV. ({detail})")


def parse_excel_headers(
    content: bytes,
    sheet: str | int = 0,
    *,
    filename: str = "",
    content_type: str = "",
) -> ParsedExcel:
    """Parse an Excel byte payload (.xlsx/.xls/.xlsm/.xlsb) into header+type metadata only.

    Robust to client paysheets: title/blank rows on top, and 1- or 2-row (merged
    section) headers. Picks the header band that yields the MOST real column names.
    Data rows are used only for local dtype inference and are then discarded;
    nothing derived from cell *values* leaves this function.
    """
    raw = _read_excel_bytes(content, sheet, filename=filename, content_type=content_type)
    return _parse_tabular(raw)


def parse_csv_headers(content: bytes) -> ParsedExcel:
    """Parse a .csv byte payload into header+type metadata only (same privacy rules)."""
    raw = _read_csv_bytes(content)
    return _parse_tabular(raw)


def _infer_type(series: pd.Series) -> str:
    kind = series.dtype.kind
    if kind in _DTYPE_MAP:
        return _DTYPE_MAP[kind]
    # object columns: try a light date sniff WITHOUT exposing values downstream
    non_null = series.dropna()
    if not non_null.empty:
        try:
            pd.to_datetime(non_null.head(20), errors="raise")
            return "date"
        except (ValueError, TypeError):
            pass
    return "string"
