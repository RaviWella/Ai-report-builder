"""Schedules router — scheduled report delivery config (FR-5.5)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import db_session
from app.core.security import BuilderRoles, require_roles
from app.core.tenancy import TenantContext, get_tenant_context
from app.domain.enums import AuditAction, ExportFormat
from app.db.metadata import ReportSchedule
from app.repositories.template_repo import TemplateRepo
from app.services.audit_service import AuditService

router = APIRouter(
    prefix="/schedules", tags=["schedules"], dependencies=[Depends(require_roles(*BuilderRoles))]
)


class ScheduleBody(BaseModel):
    template_id: str
    cron: str  # e.g. "0 6 1 * *" -> 06:00 on the 1st monthly
    recipients: list[str]
    format: ExportFormat = ExportFormat.PDF
    runtime_params: dict[str, Any] = {}
    enabled: bool = True


@router.post("")
def create_schedule(
    body: ScheduleBody,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    # Ownership check: the template must belong to the caller's tenant.
    if TemplateRepo(db).get_template(body.template_id) is None:
        raise HTTPException(status_code=404, detail="Template not found for this tenant")
    schedule = ReportSchedule(
        template_id=body.template_id,
        cron=body.cron,
        recipients=body.recipients,
        format=body.format.value,
        runtime_params=body.runtime_params,
        enabled=body.enabled,
    )
    db.add(schedule)
    db.commit()
    AuditService(db).log(
        user_id=ctx.acting_user_id,
        action=AuditAction.SCHEDULE_CREATED,
        target_type="schedule",
        target_id=schedule.id,
        detail={"cron": body.cron, "format": body.format.value},
    )
    return {"id": schedule.id, "enabled": schedule.enabled}


@router.get("")
def list_schedules(
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> list[dict]:
    repo = TemplateRepo(db)
    tenant_template_ids = {t.id for t in repo.list_templates()}
    rows = db.query(ReportSchedule).filter(
        ReportSchedule.template_id.in_(tenant_template_ids or {"__none__"})
    ).all()
    return [
        {
            "id": s.id,
            "template_id": s.template_id,
            "cron": s.cron,
            "format": s.format,
            "enabled": s.enabled,
            "recipients": s.recipients,
        }
        for s in rows
    ]
