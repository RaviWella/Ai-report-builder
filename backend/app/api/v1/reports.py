"""Reports router — run / preview (FR-V2, run-time flow)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import db_session
from app.core.security import AdminRoles, BuilderRoles, ViewerRoles, require_roles
from app.core.tenancy import TenantContext, get_tenant_context
from app.domain.report_spec import DataSpec
from app.services.report_service import ReportService

router = APIRouter(prefix="/reports", tags=["reports"])


class RunBody(BaseModel):
    params: dict[str, Any] = {}


class PreviewBody(BaseModel):
    data_spec: DataSpec
    params: dict[str, Any] = {}


def _result_payload(result) -> dict:  # noqa: ANN001
    return {
        "columns": result.columns,
        "rows": result.rows,
        "row_count": result.row_count,
        "truncated": result.truncated,
        # WS-1 provenance — lets the viewer show audit-grade lineage for a run.
        "provenance": {
            "run_id": result.run_id,
            "semantic_version_ref": result.semantic_version_ref,
            "compiled_sql_hash": result.compiled_sql_hash,
            "result_checksum": result.result_checksum,
            "datamart_snapshot_ref": result.datamart_snapshot_ref,
        },
    }


@router.get("/{template_id}/meta", dependencies=[Depends(require_roles(*ViewerRoles))])
def report_meta(
    template_id: str,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    """Kind + allowed output formats + runtime filters so the common viewer can
    render the right Generate controls for a report OR a payslip."""
    try:
        return ReportService(db).view_meta(ctx, template_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{template_id}/field-values", dependencies=[Depends(require_roles(*ViewerRoles))])
def field_values(
    template_id: str,
    ref: str,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    """Distinct values for a dimension field — populates a filter dropdown."""
    try:
        values = ReportService(db).field_values(ctx, ref)
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"values": values}


@router.get("/insights/slow-queries", dependencies=[Depends(require_roles(*BuilderRoles))])
def slow_queries(
    limit: int = 20,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    """L0 observability — the tenant's slowest query shapes (by p95 latency) from
    the run log, so a builder/admin can see what to optimise before it bites."""
    from app.services.query_insights import slow_queries as _slow

    return {"slow_queries": _slow(db, limit=min(max(limit, 1), 200))}


@router.post("/cache/warm", dependencies=[Depends(require_roles(*AdminRoles))])
def warm_cache(
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    """On-demand result-cache warming for this tenant's published reports — the same
    job the nightly beat runs. Returns {templates, warmed, skipped}."""
    from app.services.cache_warm import warm_tenant

    return warm_tenant(db, ctx.tenant_id)


@router.post("/{template_id}/run", dependencies=[Depends(require_roles(*ViewerRoles))])
def run_report(
    template_id: str,
    body: RunBody,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    try:
        result = ReportService(db).run(ctx, template_id, body.params)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _result_payload(result)


@router.post("/{template_id}/preview", dependencies=[Depends(require_roles(*ViewerRoles))])
def preview_report(
    template_id: str,
    body: RunBody,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    try:
        result = ReportService(db).run(ctx, template_id, body.params, preview=True)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _result_payload(result)


@router.post("/preview-spec", dependencies=[Depends(require_roles(*BuilderRoles))])
def preview_spec(
    body: PreviewBody,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    """Live preview of an unsaved data_spec while building (Phase 2)."""
    try:
        result = ReportService(db).preview_spec(ctx, body.data_spec, body.params)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _result_payload(result)
