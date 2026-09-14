"""Document model — a report rendered as ONE PAGE PER RECORD (vs a table of rows).

This is a general presentation mode of the common report, not an HR concept: a
payslip, a tax statement, an EPF certificate or a salary letter are all the same
shape — a per-record document with a header, identity fields, a few sections of
label→value lines (some with a total), optional one→many detail blocks (e.g. bank
accounts), and a footer. Nothing here is hard-coded to payroll; sections carry
whatever titles the uploaded layout had, and every field binding is a semantic
ref the builder/AI resolves.

Stored inside a template version's presentation_spec as
`{"kind":"document","document":<DocumentSpec>, "allowed_formats":[...]}`.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class DocumentLine(BaseModel):
    """A label/value line. `ref` None renders the label with a blank value (a line
    a tenant's data doesn't have yet) so the layout still matches their format."""

    label: str
    ref: str | None = None


class DocumentSection(BaseModel):
    """A titled group of lines, with an optional roll-up total (e.g. a section
    'Earnings' with a 'Total Earnings' line, or 'Tax' with 'Total Tax')."""

    title: str
    lines: list[DocumentLine] = Field(default_factory=list)
    total: DocumentLine | None = None


class DocumentDetailBlock(BaseModel):
    """An optional one→many block for a record (e.g. an employee's bank accounts,
    an invoice's line items). `provider` names a server-side fetcher; the block is
    generic, the provider supplies the rows."""

    title: str = "Details"
    provider: str  # e.g. "bank_instructions"
    enabled: bool = True


class DocumentSpec(BaseModel):
    title: str = "Document"
    company_name: str | None = None
    logo_data_url: str | None = None
    value_label: str = ""  # caption above the value column (e.g. "Sri Lanka Rupees")

    identity_fields: list[DocumentLine] = Field(default_factory=list)  # top key fields
    sections: list[DocumentSection] = Field(default_factory=list)
    detail_blocks: list[DocumentDetailBlock] = Field(default_factory=list)
    footer: str = ""

    # Scoping refs (configurable, NOT hard-coded): when set they become the
    # document's runtime filters so the common viewer renders the same controls.
    period_year_ref: str | None = None
    period_month_ref: str | None = None
    record_key_ref: str | None = None  # single-record filter (e.g. employee no)

    def value_refs(self) -> list[str]:
        """Every semantic ref the per-record query must select (unique, ordered)."""
        refs: list[str] = [ln.ref for ln in self.identity_fields if ln.ref]
        for s in self.sections:
            refs += [ln.ref for ln in s.lines if ln.ref]
            if s.total and s.total.ref:
                refs.append(s.total.ref)
        return list(dict.fromkeys(refs))
