"""Validations router (WS-3) — run data-quality assertions and read the latest
results for the tenant's datamart."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.services.tenant_scope import resolve_datamart_key

from app.api.deps import db_session
from app.core.security import BuilderRoles, ViewerRoles, require_roles
from app.core.tenancy import TenantContext, get_tenant_context
from app.services.coverage_audit import CoverageAuditService
from app.services.field_request_store import FieldRequestStore
from app.services.validation_service import ValidationService

router = APIRouter(prefix="/validations", tags=["validations"])


def _datamart_key(tenant_id: str) -> str:
    return resolve_datamart_key(tenant_id)


@router.post("/run", dependencies=[Depends(require_roles(*BuilderRoles))])
def run_validations(
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    return ValidationService(db).run(ctx, _datamart_key(ctx.tenant_id))


@router.get("/latest", dependencies=[Depends(require_roles(*ViewerRoles))])
def latest_validations(
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    return ValidationService(db).latest(ctx)


@router.post("/coverage", dependencies=[Depends(require_roles(*BuilderRoles))])
def coverage_audit(
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    """Data-capture coverage audit: how populated is every catalogue field's backing
    column? Flags `empty` (0% populated) and `missing` (column gone) fields — the
    data-capture gaps that make a correct mapping return a wrong-looking report."""
    return CoverageAuditService(db).run(ctx, _datamart_key(ctx.tenant_id))


class FieldRequestBody(BaseModel):
    header: str            # the heading whose data isn't captured yet
    note: str | None = None


@router.post("/field-requests", dependencies=[Depends(require_roles(*BuilderRoles))])
def request_field(
    body: FieldRequestBody,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    """Log a request for a column that has no field in the catalogue (a data-capture
    / ETL gap), so it surfaces on the Data Health dashboard instead of being faked."""
    row = FieldRequestStore(db).request(ctx.tenant_id, body.header, body.note, user_id=ctx.acting_user_id)
    if row is None:
        raise HTTPException(status_code=400, detail="A heading is required.")
    return row


@router.get("/field-requests", dependencies=[Depends(require_roles(*ViewerRoles))])
def list_field_requests(
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    """The tenant's data-capture gap list — requested-but-missing fields, for ETL."""
    return {"requests": FieldRequestStore(db).list(ctx.tenant_id)}


@router.post("/field-requests/{request_id}/resolve", dependencies=[Depends(require_roles(*BuilderRoles))])
def resolve_field_request(
    request_id: str,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    """Mark a request resolved (the field is now exposed in the datamart)."""
    row = FieldRequestStore(db).set_status(ctx.tenant_id, request_id, "resolved")
    if row is None:
        raise HTTPException(status_code=404, detail="Request not found")
    return row


@router.delete("/field-requests/{request_id}", dependencies=[Depends(require_roles(*BuilderRoles))])
def delete_field_request(
    request_id: str,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    """Remove a request from the gap list."""
    if not FieldRequestStore(db).delete_by_id(ctx.tenant_id, request_id):
        raise HTTPException(status_code=404, detail="Request not found")
    return {"deleted": request_id}
