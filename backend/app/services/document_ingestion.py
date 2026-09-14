"""Dynamic document ingestion — turn an uploaded one-page-per-record layout into
a draft DocumentSpec for review, like the report Excel flow but for a document.

Pipeline: parse the layout (generic sections, no values) -> map every line and
identity label to a semantic ref (fuzzy + AI; money lines must be MEASURES) ->
assemble a draft DocumentSpec + a review list. Scope refs (period year/month and
the per-record key) are inferred from the catalogue of the dominant entity, so a
payroll document scopes by payroll period while another report scopes by its own.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from app.core.tenancy import TenantContext
from app.domain.document_spec import DocumentDetailBlock, DocumentLine, DocumentSection, DocumentSpec
from app.domain.enums import FieldRole
from app.ingestion.document_layout import parse_document_layout
from app.services.ai_service import AIService

_DEFAULT_FOOTER = "This is a computer generated document."


@dataclass
class DocumentDraft:
    spec: DocumentSpec
    review: list[dict] = field(default_factory=list)  # [{label, section, role, ref, confidence}]
    unmatched: list[str] = field(default_factory=list)


def build_document_from_excel(ai: AIService, ctx: TenantContext, content: bytes) -> DocumentDraft:
    layout = parse_document_layout(content)
    catalog = ai.semantic.get_active_catalog(ctx.tenant_id)
    roles = {ref: f.role for ref, f in catalog.field_index().items()}

    # Map identity labels + every section line/total label in one pass.
    labels: list[str] = list(layout.identity_labels)
    for s in layout.sections:
        labels += s.line_labels
        if s.total_label:
            labels.append(s.total_label)
    mapped = ai.map_labels(ctx, labels)
    ref_of = {m["header"]: m.get("suggested_ref") for m in mapped}
    conf_of = {m["header"]: m.get("confidence", 0.0) for m in mapped}

    review: list[dict] = []
    unmatched: list[str] = []

    def money_ref(label: str, section_title: str) -> str | None:
        ref = ref_of.get(label)
        ref = ref if (ref and roles.get(ref) == FieldRole.MEASURE) else None
        review.append({"label": label, "section": section_title, "role": "measure",
                       "ref": ref, "confidence": conf_of.get(label, 0.0)})
        if ref is None:
            unmatched.append(label)
        return ref

    # Identity fields (dimensions are fine here).
    identity = [DocumentLine(label=lbl, ref=ref_of.get(lbl)) for lbl in layout.identity_labels]
    for ln in identity:
        review.append({"label": ln.label, "section": "(identity)", "role": "dimension",
                       "ref": ln.ref, "confidence": conf_of.get(ln.label, 0.0)})

    sections = [
        DocumentSection(
            title=s.title,
            lines=[DocumentLine(label=lbl, ref=money_ref(lbl, s.title)) for lbl in s.line_labels],
            total=(DocumentLine(label=s.total_label, ref=money_ref(s.total_label, s.title))
                   if s.total_label else None),
        )
        for s in layout.sections
    ]

    spec = DocumentSpec(
        title=layout.company_name or "Document",
        company_name=layout.company_name,
        value_label=layout.value_label or "",
        footer=layout.footer or _DEFAULT_FOOTER,
        identity_fields=identity,
        sections=sections,
        detail_blocks=[DocumentDetailBlock(title=t, provider=p) for t, p in layout.detail_blocks],
    )

    # Scope: infer period + record-key refs from the dominant entity's catalogue.
    dominant = _dominant_entity(spec.value_refs())
    if dominant:
        spec.period_year_ref, spec.period_month_ref = _period_refs(catalog, dominant)
    spec.record_key_ref = next((ln.ref for ln in identity if ln.ref), None)

    return DocumentDraft(spec=spec, review=review, unmatched=unmatched)


def _dominant_entity(refs: list[str]) -> str | None:
    counts = Counter(r.split(".", 1)[0] for r in refs if "." in r)
    return counts.most_common(1)[0][0] if counts else None


def _period_refs(catalog, entity_key: str) -> tuple[str | None, str | None]:  # noqa: ANN001
    """Find this entity's year/month dimension refs (e.g. paysheet.payroll_year),
    so the document can be scoped to a period without hard-coding the columns."""
    year_ref = month_ref = None
    for ref, f in catalog.field_index().items():
        if not ref.startswith(f"{entity_key}.") or f.role != FieldRole.DIMENSION:
            continue
        tail = ref.split(".", 1)[1].lower()
        if year_ref is None and ("payroll_year" in tail or tail == "year" or tail.endswith("_year")):
            year_ref = ref
        if month_ref is None and ("payroll_month" in tail or tail == "month" or tail.endswith("_month")):
            month_ref = ref
    return year_ref, month_ref
