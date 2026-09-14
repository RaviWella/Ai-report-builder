"""Canvas design model — the block-based layout behind a LETTER or EMAIL document.

Where DocumentSpec (document_spec.py) is a structured per-record payslip/statement,
a DocumentDesign is a freeform page a builder composes on a canvas: a stack of
blocks (rich text, a bound field, a logo, a data table, a divider…) that render to
one page per record for letters, or one HTML body for emails.

Data binding is by MERGE TOKEN: rich-text blocks embed `{{semantic.ref}}` tokens,
and field/table blocks name refs directly. Nothing is hard-coded to HR — every ref
is resolved against the tenant's semantic catalogue, exactly like reports.

A token may also carry a VALUE MAP: `{{ref|value=text|value=text|default=text}}`
renders different literal text depending on the field's own value for that
record — e.g. `{{employee.gender|Male=he|Female=she|default=they}}` — rather
than the raw value itself. Generic (works for any dimension, not just gender);
`default` is used when the record's value matches none of the given keys, else
the raw value is shown as before.

Stored inside a template version's presentation_spec as
    {"kind":"document","doc_type":"letter|email","design":<DocumentDesign>, ...}
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field

# Captures a token's full inner content; the ref/value-map split happens in
# parse_token() since a value map's replacement text isn't itself ref-shaped.
TOKEN_RE = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")
_REF_RE = re.compile(r"^[a-zA-Z0-9_.]+$")


def parse_token(inner: str) -> tuple[str, dict[str, str]] | None:
    """Split one token's inner content into (ref, value_map). value_map is {}
    for a plain {{ref}}. Returns None if the ref part isn't actually ref-shaped
    (e.g. unrelated curly-brace text) — callers should leave those untouched."""
    parts = [p.strip() for p in inner.split("|")]
    ref = parts[0]
    if not _REF_RE.match(ref):
        return None
    value_map: dict[str, str] = {}
    for part in parts[1:]:
        key, sep, text = part.partition("=")
        if sep:
            value_map[key.strip()] = text.strip()
    return ref, value_map


def extract_tokens(html: str | None) -> list[str]:
    """Semantic refs referenced by `{{ref}}` (or `{{ref|value=text|...}}`) tokens
    inside a rich-text/subject string."""
    if not html:
        return []
    refs = []
    for inner in TOKEN_RE.findall(html):
        parsed = parse_token(inner)
        if parsed:
            refs.append(parsed[0])
    return refs


class DesignColumn(BaseModel):
    """A column of a data-bound table block."""

    ref: str
    label: str | None = None
    total: bool = False


class DesignManualField(BaseModel):
    """A value the issuer types at generation time (not from data), e.g. an effective
    date. Referenced by the token `{{manual.<key>}}`."""

    key: str
    label: str


class DesignBlock(BaseModel):
    """One block on the canvas. `type` selects how it renders; unused fields stay None.

    - text:      `html` rich text, may embed `{{ref}}` merge tokens
    - field:     a single bound value — `ref` (+ `label`, `prefix`, `suffix`)
    - image:     `src` data-URL (logo, signature image)
    - table:     data-bound rows — `columns` (list of DesignColumn), one row per
                 detail record via `provider`, or the record's own values
    - divider / spacer: layout only
    - signature: a labelled signature line
    """

    id: str
    type: str  # text | field | image | table | divider | spacer | signature
    html: str | None = None
    ref: str | None = None
    label: str | None = None
    prefix: str | None = None
    suffix: str | None = None
    src: str | None = None
    provider: str | None = None  # table block: one→many provider name
    columns: list[DesignColumn] = Field(default_factory=list)
    align: str | None = None  # left | center | right
    width_pct: int | None = None  # image/table width as % of content width
    height_px: int | None = None  # spacer height
    style: dict[str, Any] = Field(default_factory=dict)  # fontSize, color, fontWeight, marginTop…


class DocumentDesign(BaseModel):
    page_size: str = "A4"
    orientation: str = "portrait"  # portrait | landscape
    margin_mm: int = 20  # uniform default; per-side values below override it when set
    margin_top: int | None = None
    margin_right: int | None = None
    margin_bottom: int | None = None
    margin_left: int | None = None
    company_name: str | None = None
    header_html: str | None = None  # repeated at the top of each record page (tokens ok)
    footer_html: str | None = None  # repeated at the foot of each record page (tokens ok)
    show_page_numbers: bool = False
    manual_fields: list[DesignManualField] = Field(default_factory=list)  # filled at issuance
    blocks: list[DesignBlock] = Field(default_factory=list)

    # Scoping refs (configurable, NOT hard-coded) — become the document's runtime
    # filters so the common viewer/generate flow renders the right controls.
    period_year_ref: str | None = None
    period_month_ref: str | None = None
    record_key_ref: str | None = None  # one page/email per matching record

    def margins(self) -> tuple[int, int, int, int]:
        """(top, right, bottom, left) in mm — per-side value or the uniform default."""
        m = self.margin_mm
        return (
            self.margin_top if self.margin_top is not None else m,
            self.margin_right if self.margin_right is not None else m,
            self.margin_bottom if self.margin_bottom is not None else m,
            self.margin_left if self.margin_left is not None else m,
        )

    def value_refs(self) -> list[str]:
        """Every semantic ref the per-record query must select (unique, ordered):
        field blocks, table columns, `{{ref}}` tokens in text blocks + header/footer."""
        refs: list[str] = extract_tokens(self.header_html) + extract_tokens(self.footer_html)
        for b in self.blocks:
            if b.ref:
                refs.append(b.ref)
            refs += extract_tokens(b.html)
            refs += [c.ref for c in b.columns if c.ref]
        # manual.* (issuer-typed) and system.* (today's date etc.) aren't queried.
        return [r for r in dict.fromkeys(refs) if not r.startswith(("manual.", "system."))]
