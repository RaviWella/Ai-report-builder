"""Templates router — CRUD + versioning lifecycle (FR-B10, SRS §7)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import db_session
from app.core.crypto import SecretError, decrypt_bytes, encrypt_bytes
from app.core.security import BuilderRoles, require_roles
from app.core.tenancy import TenantContext, get_tenant_context
from app.db.metadata import TemplateUpload
from app.domain.report_spec import DataSpec, PresentationSpec
from app.repositories.template_repo import TemplateRepo
from app.services.template_kind import allowed_formats, kind_of
from app.services.template_service import DraftInput, TemplateService

# Cap the stored source file — a mapping preview needs the sheet, not a data lake.
_MAX_SOURCE_BYTES = 20 * 1024 * 1024  # 20 MB

router = APIRouter(prefix="/templates", tags=["templates"])


class CreateTemplateBody(BaseModel):
    name: str
    description: str | None = None
    module: str = "General"


class RenameBody(BaseModel):
    name: str | None = None
    module: str | None = None
    description: str | None = None


class DraftBody(BaseModel):
    data_spec: DataSpec
    presentation_spec: PresentationSpec


@router.get("")
def list_templates(
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> list[dict]:
    repo = TemplateRepo(db)
    rows = repo.list_templates()
    out = []
    for t in rows:
        # Reports and payslips share this table; tag each with its kind + allowed
        # output formats so the common viewer can render the right controls.
        ver = repo.get_published_version(t.id) or repo.latest_version(t.id)
        ps = (ver.presentation_spec if ver else None) or {}
        out.append(
            {
                "id": t.id,
                "name": t.name,
                "description": t.description,
                "module": t.module,
                "current_published_version_id": t.current_published_version_id,
                "kind": kind_of(ps),
                "allowed_formats": allowed_formats(ps),
            }
        )
    return out


@router.post("", dependencies=[Depends(require_roles(*BuilderRoles))])
def create_template(
    body: CreateTemplateBody,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    tpl = TemplateService(db).create_template(
        ctx, name=body.name, description=body.description, module=body.module
    )
    return {"id": tpl.id, "name": tpl.name, "module": tpl.module}


class RuleReportBody(BaseModel):
    name: str
    description: str | None = None
    category: str = "General"   # the module/category it's filed under on the Templates page
    labels: dict[str, str] = {}  # friendly column titles: output column -> display name
    new_version: bool = False   # update: snapshot a new version (else update in place)
    note: str = ""              # a comment describing what changed (for a new version)
    export_options: dict = {}   # export header: {description, show_company, show_meta}
    row_number_column: str | None = None  # e.g. "s_no" — numbers rows 1..N
    subtotal: dict | None = None  # {group_by, sum_columns, label_column, label} -> Total rows
    totals: list[str] = []  # `output` column names to sum in the Excel/PDF grand-total row
    pivot: dict | None = None  # PivotSpec — reshape long rows into a wide, dynamic-column grid
    session_id: str | None = None  # the AI chat session this save came from, if any — lets
    # reopening the report to edit it resume that SAME conversation (see
    # ReportService.rule_report_chat_session / ChatHistoryService.get_for_template)
    spec: dict  # a RuleReportSpec (validated server-side)


@router.post("/rule-report", dependencies=[Depends(require_roles(*BuilderRoles))])
def create_rule_report(
    body: RuleReportBody,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    """Create + publish a governed rule-engine report from a JSON spec. It then runs
    and exports through the normal /reports endpoints — no per-report code."""
    from pydantic import ValidationError

    from app.services.report_service import ReportService

    try:
        return ReportService(db).create_rule_report(
            ctx, name=body.name, spec=body.spec, description=body.description,
            category=body.category, labels=body.labels, export_options=body.export_options,
            row_number_column=body.row_number_column, subtotal=body.subtotal, totals=body.totals,
            pivot=body.pivot, session_id=body.session_id,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid rule spec: {exc.errors()[0]['msg']}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


class ExplainBody(BaseModel):
    spec: dict
    labels: dict[str, str] = {}


@router.post("/rule-report/explain", dependencies=[Depends(require_roles(*BuilderRoles))])
def explain_rule_report(body: ExplainBody) -> dict:
    """Paraphrase a rule spec into plain, HR-readable language (no save). Used by the
    builder's "In plain words" tab so a non-technical reader can follow the logic."""
    from pydantic import ValidationError

    from app.domain.rule_report import RuleReportSpec
    from app.services.rule_explain import explain_spec

    try:
        spec = RuleReportSpec.model_validate(body.spec)
    except (ValidationError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Spec isn’t complete enough to explain yet.") from exc
    return explain_spec(spec, body.labels)


@router.get("/rule-report/{template_id}/chat-session", dependencies=[Depends(require_roles(*BuilderRoles))])
def rule_report_chat_session(
    template_id: str,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    """The chat conversation linked to this report (if any), so reopening it
    to edit can resume that SAME conversation — visible to any builder in the
    tenant, not just whoever originally built it. `session: null` (not an
    error) when the report has no linked chat (built before this feature, or
    via raw JSON) or its session was since deleted."""
    from app.services.report_service import ReportService

    return {"session": ReportService(db).rule_report_chat_session(ctx, template_id)}


@router.put("/rule-report/{template_id}", dependencies=[Depends(require_roles(*BuilderRoles))])
def update_rule_report(
    template_id: str,
    body: RuleReportBody,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    """Re-validate + publish a new version of an existing rule report (spec, name,
    category, column titles)."""
    from pydantic import ValidationError

    from app.services.report_service import ReportService

    try:
        return ReportService(db).update_rule_report(
            ctx, template_id, name=body.name, spec=body.spec, description=body.description,
            category=body.category, labels=body.labels,
            new_version=body.new_version, note=body.note, export_options=body.export_options,
            row_number_column=body.row_number_column, subtotal=body.subtotal, totals=body.totals,
            pivot=body.pivot, session_id=body.session_id,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid rule spec: {exc.errors()[0]['msg']}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/{template_id}", dependencies=[Depends(require_roles(*BuilderRoles))])
def rename_template(
    template_id: str,
    body: RenameBody,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    try:
        tpl = TemplateService(db).rename(
            ctx, template_id, name=body.name, module=body.module, description=body.description
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"id": tpl.id, "name": tpl.name, "module": tpl.module, "description": tpl.description}


@router.post("/{template_id}/draft", dependencies=[Depends(require_roles(*BuilderRoles))])
def save_draft(
    template_id: str,
    body: DraftBody,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    try:
        version = TemplateService(db).save_draft(
            ctx, template_id, DraftInput(body.data_spec, body.presentation_spec)
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"version_id": version.id, "version_no": version.version_no, "status": version.status}


@router.post("/{template_id}/versions/{version_id}/publish",
             dependencies=[Depends(require_roles(*BuilderRoles))])
def publish(
    template_id: str,
    version_id: str,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    try:
        version = TemplateService(db).publish(ctx, template_id, version_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"version_id": version.id, "status": version.status}


@router.post("/{template_id}/versions/{version_id}/rollback",
             dependencies=[Depends(require_roles(*BuilderRoles))])
def rollback(
    template_id: str,
    version_id: str,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    try:
        version = TemplateService(db).rollback(ctx, template_id, version_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"published_version_id": version.id, "version_no": version.version_no}


@router.get("/{template_id}/draft")
def get_draft(
    template_id: str,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    """Latest saved spec for a template — used to load it back into the builder."""
    try:
        tpl, version = TemplateService(db).latest_spec(ctx, template_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if version is None:
        raise HTTPException(status_code=404, detail="This report has no saved version yet")
    return {
        "name": tpl.name,
        "module": tpl.module,
        "description": tpl.description,
        "data_spec": version.data_spec,
        "presentation_spec": version.presentation_spec,
    }


@router.put("/{template_id}/source-file", dependencies=[Depends(require_roles(*BuilderRoles))])
async def upload_source_file(
    template_id: str,
    file: UploadFile = File(...),
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    """Store the source sheet a template was built from — ENCRYPTED at rest, one per
    template (upsert). Lets a builder re-open and preview the exact file on edit."""
    tpl = TemplateRepo(db).get_template(template_id)
    if tpl is None:
        raise HTTPException(status_code=404, detail="Report template not found")
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(raw) > _MAX_SOURCE_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 20 MB)")
    try:
        ciphertext = encrypt_bytes(raw)
    except SecretError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    row = db.get(TemplateUpload, template_id)
    if row is None:
        row = TemplateUpload(template_id=template_id)
        db.add(row)
    row.filename = file.filename or "upload.xlsx"
    row.content_type = file.content_type or "application/octet-stream"
    row.content_enc = ciphertext
    row.size_bytes = len(raw)
    row.created_by = ctx.acting_user_id
    db.commit()
    return {"template_id": template_id, "filename": row.filename, "size_bytes": row.size_bytes}


@router.get("/{template_id}/source-file/meta")
def source_file_meta(
    template_id: str,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    """Whether a stored source file exists (so the UI can offer 'View file' on edit)."""
    if TemplateRepo(db).get_template(template_id) is None:
        raise HTTPException(status_code=404, detail="Report template not found")
    row = db.get(TemplateUpload, template_id)
    if row is None:
        return {"exists": False}
    return {
        "exists": True,
        "filename": row.filename,
        "content_type": row.content_type,
        "size_bytes": row.size_bytes,
    }


@router.get("/{template_id}/source-file", dependencies=[Depends(require_roles(*BuilderRoles))])
def download_source_file(
    template_id: str,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> Response:
    """Return the decrypted source file so the builder can preview it on edit."""
    if TemplateRepo(db).get_template(template_id) is None:
        raise HTTPException(status_code=404, detail="Report template not found")
    row = db.get(TemplateUpload, template_id)
    if row is None:
        raise HTTPException(status_code=404, detail="No source file stored for this template")
    try:
        raw = decrypt_bytes(row.content_enc)
    except SecretError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return Response(
        content=raw,
        media_type=row.content_type or "application/octet-stream",
        headers={"Content-Disposition": f'inline; filename="{row.filename}"'},
    )


@router.delete("/{template_id}/source-file", dependencies=[Depends(require_roles(*BuilderRoles))])
def delete_source_file(
    template_id: str,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    """Forget the stored source file (privacy — a builder can remove it any time)."""
    if TemplateRepo(db).get_template(template_id) is None:
        raise HTTPException(status_code=404, detail="Report template not found")
    row = db.get(TemplateUpload, template_id)
    if row is not None:
        db.delete(row)
        db.commit()
    return {"deleted": template_id}


@router.delete("/{template_id}", dependencies=[Depends(require_roles(*BuilderRoles))])
def delete_template(
    template_id: str,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    try:
        TemplateService(db).delete_template(ctx, template_id)
        db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"deleted": template_id}


@router.get("/{template_id}/versions")
def list_versions(
    template_id: str,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> list[dict]:
    repo = TemplateRepo(db)
    tpl = repo.get_template(template_id)
    if tpl is None:
        raise HTTPException(status_code=404, detail="Template not found")
    return [
        {
            "id": v.id,
            "version_no": v.version_no,
            "status": v.status,
            "semantic_version_ref": v.semantic_version_ref,
            "created_at": v.created_at.isoformat() if v.created_at else None,
            "note": (v.presentation_spec or {}).get("note", ""),
            "is_current": v.id == tpl.current_published_version_id,
        }
        for v in repo.list_versions(template_id)
    ]
