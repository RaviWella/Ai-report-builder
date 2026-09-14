"""Exports router — branded Excel / PDF download (FR-V3, FR-B11)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import db_session
from app.core.security import ViewerRoles, require_roles
from app.core.tenancy import TenantContext, get_tenant_context
from app.domain.enums import ExportFormat
from app.services.report_service import ReportService
from app.workers.tasks import async_export

router = APIRouter(prefix="/exports", tags=["exports"])


class ExportBody(BaseModel):
    params: dict[str, Any] = {}
    format: ExportFormat = ExportFormat.XLSX
    async_job: bool = False


@router.post("/{template_id}", dependencies=[Depends(require_roles(*ViewerRoles))])
def export_report(
    template_id: str,
    body: ExportBody,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
):
    if body.async_job:
        task = async_export.delay(template_id, ctx.tenant_id, body.params, body.format.value)
        return {"job_id": task.id, "status": "queued"}

    try:
        content, mime = ReportService(db).export(ctx, template_id, body.params, body.format)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    ext = "xlsx" if body.format == ExportFormat.XLSX else "pdf"
    return Response(
        content=content,
        media_type=mime,
        headers={"Content-Disposition": f'attachment; filename="report_{template_id}.{ext}"'},
    )
