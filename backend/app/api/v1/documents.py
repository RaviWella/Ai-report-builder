"""Documents router — dynamic per-record documents (one PDF page per record).
Upload a layout, review the auto-mapping, save a template, then render PDFs.
Generic: a payslip, tax statement, certificate, etc. are all documents.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import db_session
from app.core.security import BuilderRoles, ViewerRoles, require_roles
from app.core.tenancy import TenantContext, get_tenant_context
from app.domain.document_design import DocumentDesign
from app.domain.document_spec import DocumentSpec
from app.services.ai_service import AIService
from app.services.document_category_service import DocumentCategoryService
from app.services.document_sample import (
    ai_enhance_design, build_design_from_sample, map_word_fields_design,
)
from app.services.document_service import DocumentService
from app.services.letterhead_service import LetterheadService
from app.services.manual_field_service import ManualFieldService

router = APIRouter(prefix="/documents", tags=["documents"])


class SaveBody(BaseModel):
    name: str
    doc_type: str = "report"  # letter | email | report
    category: str = "General"
    # report-doc uses `document`; letter/email use `design` (+ email `subject`)
    document: DocumentSpec | None = None
    design: DocumentDesign | None = None
    subject: str | None = None
    publish: bool = False
    allowed_formats: list[str] | None = None
    # accept the legacy `module` field name as the category, for older callers
    module: str | None = None


class RenderBody(BaseModel):
    year: int | None = None
    month: int | None = None
    record_key: str | None = None
    max_records: int | None = None
    labelled: bool = False  # preview: show [Field Label] placeholders instead of data
    manual: dict[str, str] = {}  # issuer-typed values for {{manual.key}} tokens
    fmt: str = "pdf"  # render format: "pdf" or "docx" (editable Word, letters only)


class CategoryBody(BaseModel):
    doc_type: str
    name: str


class RenameCategoryBody(BaseModel):
    name: str


def _category_of(body: SaveBody) -> str:
    return body.category or body.module or "General"


@router.post("/ingest", dependencies=[Depends(require_roles(*BuilderRoles))])
async def ingest(
    file: UploadFile = File(...),
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    """Upload a per-record layout. We recover its document structure and map each
    line to a semantic field (fuzzy + AI). Only labels leave the parser."""
    content = await file.read()
    try:
        draft = DocumentService(db).ingest(ctx, content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Could not read that layout: {exc}") from exc
    return {
        "spec": draft.spec.model_dump(mode="json"),
        "review": draft.review,
        "unmatched": draft.unmatched,
        "note": "Only labels were read; values/record data were not.",
    }


@router.post("", dependencies=[Depends(require_roles(*BuilderRoles))])
def create(
    body: SaveBody,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    try:
        return DocumentService(db).create(
            ctx, name=body.name, category=_category_of(body), doc_type=body.doc_type,
            document=body.document, design=body.design, email_subject=body.subject,
            publish=body.publish, allowed_formats=body.allowed_formats,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("", dependencies=[Depends(require_roles(*ViewerRoles))])
def list_documents(
    doc_type: str | None = None,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    return {"documents": DocumentService(db).list(ctx, doc_type)}


@router.post("/design/from-sample", dependencies=[Depends(require_roles(*BuilderRoles))])
async def design_from_sample(
    file: UploadFile = File(...),
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    """Upload a sample letter (Word / PDF / image / Excel). We extract its text locally,
    turn it into a canvas design and auto-map 'Label: value' lines to fields as
    {{tokens}} for review. Only labels are read; the sample's values are not."""
    content = await file.read()
    try:
        return build_design_from_sample(
            AIService(db), ctx, content, file.filename or "", file.content_type or "",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


class EnhanceBody(BaseModel):
    design: DocumentDesign


@router.post("/design/map-word-fields", dependencies=[Depends(require_roles(*BuilderRoles))])
def design_map_word_fields(
    body: EnhanceBody,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    """Deterministic: bind leftover Word «Field» markers through the catalogue matcher."""
    return map_word_fields_design(AIService(db), ctx, body.design.model_dump(mode="json"))


@router.post("/design/ai-enhance", dependencies=[Depends(require_roles(*BuilderRoles))])
def design_ai_enhance(
    body: EnhanceBody,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    """Opt-in: map any remaining dynamic values in the current design with the AI
    (slower — one LLM call). Only used when the user clicks 'Smart map with AI'."""
    try:
        return ai_enhance_design(AIService(db), ctx, body.design.model_dump(mode="json"))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


class LetterheadBody(BaseModel):
    name: str | None = None
    logo_data_url: str | None = None
    header_html: str | None = None
    footer_html: str | None = None


@router.get("/letterheads", dependencies=[Depends(require_roles(*ViewerRoles))])
def list_letterheads(
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    return {"letterheads": LetterheadService(db).list(ctx)}


@router.post("/letterheads", dependencies=[Depends(require_roles(*BuilderRoles))])
def create_letterhead(
    body: LetterheadBody,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    try:
        return LetterheadService(db).create(
            ctx, name=body.name or "", logo_data_url=body.logo_data_url,
            header_html=body.header_html, footer_html=body.footer_html,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/letterheads/{letterhead_id}", dependencies=[Depends(require_roles(*BuilderRoles))])
def update_letterhead(
    letterhead_id: str,
    body: LetterheadBody,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    try:
        return LetterheadService(db).update(
            ctx, letterhead_id, name=body.name, logo_data_url=body.logo_data_url,
            header_html=body.header_html, footer_html=body.footer_html,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/letterheads/{letterhead_id}", dependencies=[Depends(require_roles(*BuilderRoles))])
def delete_letterhead(
    letterhead_id: str,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    LetterheadService(db).delete(ctx, letterhead_id)
    return {"deleted": letterhead_id}


# ---- manual-field pool (per-tenant; declared BEFORE /{template_id}) ---------------- #
class ManualFieldBody(BaseModel):
    label: str
    key: str | None = None


@router.get("/manual-fields", dependencies=[Depends(require_roles(*ViewerRoles))])
def list_manual_fields(
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    return {"manual_fields": ManualFieldService(db).list(ctx)}


@router.post("/manual-fields", dependencies=[Depends(require_roles(*BuilderRoles))])
def create_manual_field(
    body: ManualFieldBody,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    try:
        return ManualFieldService(db).create(ctx, label=body.label, key=body.key)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/manual-fields/{field_id}", dependencies=[Depends(require_roles(*BuilderRoles))])
def delete_manual_field(
    field_id: str,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    ManualFieldService(db).delete(ctx, field_id)
    return {"deleted": field_id}


# ---- categories (declared BEFORE /{template_id} so 'categories' isn't captured) --- #
@router.get("/categories", dependencies=[Depends(require_roles(*ViewerRoles))])
def list_categories(
    doc_type: str,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    return {"categories": DocumentCategoryService(db).list(ctx, doc_type)}


@router.post("/categories", dependencies=[Depends(require_roles(*BuilderRoles))])
def create_category(
    body: CategoryBody,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    try:
        return DocumentCategoryService(db).create(ctx, body.doc_type, body.name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/categories/{category_id}", dependencies=[Depends(require_roles(*BuilderRoles))])
def rename_category(
    category_id: str,
    body: RenameCategoryBody,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    try:
        return DocumentCategoryService(db).rename(ctx, category_id, body.name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/categories/{category_id}", dependencies=[Depends(require_roles(*BuilderRoles))])
def delete_category(
    category_id: str,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    DocumentCategoryService(db).delete(ctx, category_id)
    return {"deleted": category_id}


@router.get("/{template_id}", dependencies=[Depends(require_roles(*BuilderRoles))])
def get_document(
    template_id: str,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    try:
        return DocumentService(db).get(ctx, template_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/{template_id}", dependencies=[Depends(require_roles(*BuilderRoles))])
def update_document(
    template_id: str,
    body: SaveBody,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    try:
        return DocumentService(db).update(
            ctx, template_id, name=body.name, category=_category_of(body), doc_type=body.doc_type,
            document=body.document, design=body.design, email_subject=body.subject,
            publish=body.publish, allowed_formats=body.allowed_formats,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


class StatusBody(BaseModel):
    status: str  # active | inactive | archived | draft


@router.patch("/{template_id}/status", dependencies=[Depends(require_roles(*BuilderRoles))])
def set_status(
    template_id: str,
    body: StatusBody,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    """Move a document through its lifecycle (Active / Inactive / Archived / Draft)."""
    try:
        return DocumentService(db).set_status(ctx, template_id, body.status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{template_id}/duplicate", dependencies=[Depends(require_roles(*BuilderRoles))])
def duplicate_document(
    template_id: str,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    """Copy an existing document as a new draft (start-from: copy existing)."""
    try:
        return DocumentService(db).duplicate(ctx, template_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{template_id}/preview", dependencies=[Depends(require_roles(*ViewerRoles))])
def preview(
    template_id: str,
    body: RenderBody,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    """In-browser preview for letter/email — composed HTML (+ subject) for one record."""
    try:
        return DocumentService(db).preview(
            ctx, template_id, year=body.year, month=body.month, record_key=body.record_key,
            labelled=body.labelled, manual=body.manual,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{template_id}/render", dependencies=[Depends(require_roles(*ViewerRoles))])
def render(
    template_id: str,
    body: RenderBody,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> Response:
    fmt = "docx" if body.fmt == "docx" else "pdf"
    try:
        data = DocumentService(db).render(
            ctx, template_id, year=body.year, month=body.month,
            record_key=body.record_key, max_records=body.max_records, manual=body.manual,
            fmt=fmt,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    media, ext = (
        ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "docx")
        if fmt == "docx" else ("application/pdf", "pdf")
    )
    return Response(
        content=data, media_type=media,
        headers={"Content-Disposition": f'attachment; filename="document_{template_id}.{ext}"'},
    )
