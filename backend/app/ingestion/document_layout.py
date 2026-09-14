"""Document layout ingestion — read an uploaded one-page-per-record layout (Excel)
and recover its DOCUMENT structure: header, identity fields, titled sections of
label lines (with optional totals), and one→many detail blocks.

Generic, not HR-specific: section titles are whatever the sheet used. Sections are
delimited structurally (a 'Total …' / 'Net …' line closes a section, the next
content row starts the next one), so it works for a payslip, a tax statement, a
certificate, etc. Only labels are read — never values/PII.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field

import openpyxl

_TOTAL_HINT = re.compile(r"^\s*total\b", re.I)
_NET_HINT = re.compile(r"^\s*net\b", re.I)
_DETAIL_HINT = re.compile(r"\bbank\b", re.I)  # one built-in detail provider for now
_SKIP_LABELS = {"logo", "description", "unit", "amount", "rs", "value"}
_IDENTITY_MAXLEN = 40


@dataclass
class RawSection:
    title: str
    line_labels: list[str] = field(default_factory=list)
    total_label: str | None = None


@dataclass
class DocumentLayout:
    company_name: str | None = None
    value_label: str | None = None
    identity_labels: list[str] = field(default_factory=list)
    sections: list[RawSection] = field(default_factory=list)
    detail_blocks: list[tuple[str, str]] = field(default_factory=list)  # (title, provider)
    footer: str | None = None
    sheet_name: str | None = None


def _txt(v: object) -> str:
    if v is None:
        return ""
    s = str(v).strip()
    return "" if s.lower() == "nan" else s


def parse_document_layout(content: bytes, sheet: str | int | None = None) -> DocumentLayout:
    wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True, read_only=True)
    ws = wb[sheet] if isinstance(sheet, str) else wb.worksheets[sheet or 0]
    out = DocumentLayout(sheet_name=ws.title)

    max_col = min(ws.max_column or 1, 8)
    max_row = ws.max_row or 0

    current: RawSection | None = None
    body = False       # False = top header/identity zone; True = the line table
    in_detail = False  # inside a one→many detail block (its sub-lines are provider-supplied)
    just_closed = False

    def push() -> None:
        nonlocal current
        if current is not None:
            out.sections.append(current)
            current = None

    for r in range(1, max_row + 1):
        cells = [_txt(ws.cell(row=r, column=c).value) for c in range(1, max_col + 1)]
        nonblank = [c for c in cells if c]
        if not nonblank:
            continue
        label = nonblank[0]
        low = label.lower()
        row_low = " ".join(cells).lower()
        has_colon = any(c == ":" for c in cells[1:])

        if low == "logo":
            if len(nonblank) > 1:
                out.company_name = out.company_name or nonblank[1]
            continue
        if len(label) > _IDENTITY_MAXLEN and " " in label:
            out.footer = label
            continue
        if "rupee" in low or re.search(r"\b(lkr|rs\.?)\b", low):
            out.value_label = label
            continue
        # The "Description | … | Amount" row separates the header/identity zone
        # from the line table.
        if "description" in row_low and ("amount" in row_low or "value" in row_low):
            body = True
            continue

        if not body:
            # Header/identity zone: keep "label : value" rows as identity; the
            # rest (period subtitle etc.) is header chrome we don't map.
            if has_colon:
                out.identity_labels.append(label)
            continue

        if low in _SKIP_LABELS:
            continue
        # Once inside a detail block, its sub-lines are supplied by the provider.
        if in_detail:
            continue

        # Detail block (one→many child rows), e.g. "Bank Details".
        if _DETAIL_HINT.search(low):
            push()
            out.detail_blocks.append((label, "bank_instructions"))
            in_detail = True
            just_closed = False
            continue

        # A "Total …" closes the current section as its roll-up.
        if _TOTAL_HINT.search(label):
            if current is None:
                current = RawSection(title="")
            current.total_label = label
            push()
            just_closed = True
            continue
        # A "Net …" is a standalone highlighted total (its own one-line section).
        if _NET_HINT.search(label):
            push()
            out.sections.append(RawSection(title="", total_label=label))
            just_closed = True
            continue

        # Section header: an explicit "Title:" OR the first row after a section
        # closed (Total/Net). Otherwise it's a line in the current section.
        if label.rstrip().endswith(":") or just_closed:
            push()
            current = RawSection(title=label.rstrip(":").strip())
            just_closed = False
            continue

        if current is None:
            current = RawSection(title="")
        current.line_labels.append(label)
        just_closed = False

    push()
    wb.close()
    # Drop empty sections that are neither titled nor carrying a total/lines.
    out.sections = [s for s in out.sections if s.title or s.line_labels or s.total_label]
    return out
