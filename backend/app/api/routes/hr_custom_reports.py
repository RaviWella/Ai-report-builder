"""Custom reports API — list custom_reports views and export to Excel or PDF."""
from __future__ import annotations

import io
from typing import List, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_tenant, verify_api_key
from app.schemas.auth import TenantContext
from app.schemas.custom_reports import (
    CustomReportDefinitionCreate,
    CustomReportDefinitionOut,
    CustomReportDefinitionUpdate,
    CustomReportSyncResponse,
)
from app.services.hr_etl import custom_reports_admin, custom_reports_data
from app.services.hr_etl.custom_reports_data import ExportFilters, parse_column_filters_json
from app.services.hr_etl.schema_names import custom_reports_schema

router = APIRouter()
_EXPORT_MEDIA_TYPES = {
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf": "application/pdf",
}


def _pg(tenant_id: str):
    from app.core.warehouse import get_warehouse_engine_sync

    return get_warehouse_engine_sync(tenant_id)


def _export_filters(
    proc_year: int | None,
    proc_month: int | None,
    emp_no: str | None,
    column_filters: str | None = None,
) -> ExportFilters:
    return ExportFilters(
        proc_year=proc_year,
        proc_month=proc_month,
        emp_no=emp_no.strip() if emp_no else None,
        column_filters=parse_column_filters_json(column_filters),
    )


@router.get("/custom-reports")
def list_custom_reports(
    module: str | None = None,
    ctx: TenantContext = Depends(get_current_tenant),
    _: str = Depends(verify_api_key),
):
    views = custom_reports_data.list_custom_report_views(
        _pg(ctx.tenant_id),
        ctx.tenant_id,
        module=module,
    )
    return {
        "tenant_id": ctx.tenant_id,
        "schema": views[0]["schema"] if views else custom_reports_schema(ctx.tenant_id),
        "module": module,
        "views": views,
    }


@router.get(
    "/custom-reports/definitions",
    response_model=List[CustomReportDefinitionOut],
)
def list_custom_report_definitions(
    module: str | None = None,
    include_inactive: bool = False,
    ctx: TenantContext = Depends(get_current_tenant),
    _: str = Depends(verify_api_key),
    db: Session = Depends(get_db),
):
    return custom_reports_admin.list_definitions(
        db,
        ctx.tenant_id,
        include_inactive=include_inactive,
        module=module,
    )


@router.post(
    "/custom-reports/definitions",
    response_model=CustomReportDefinitionOut,
    status_code=status.HTTP_201_CREATED,
)
def create_custom_report_definition(
    payload: CustomReportDefinitionCreate,
    ctx: TenantContext = Depends(get_current_tenant),
    _: str = Depends(verify_api_key),
    db: Session = Depends(get_db),
):
    try:
        return custom_reports_admin.create_definition(db, ctx.tenant_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except IntegrityError as exc:
        raise HTTPException(
            status_code=409,
            detail=f"View name already exists for this tenant: {payload.view_name}",
        ) from exc


@router.post(
    "/custom-reports/definitions/sync",
    response_model=CustomReportSyncResponse,
)
def sync_custom_report_definitions(
    ctx: TenantContext = Depends(get_current_tenant),
    _: str = Depends(verify_api_key),
):
    report = custom_reports_admin.run_sync(ctx.tenant_id)
    return CustomReportSyncResponse(
        tenant_id=report.tenant_id,
        warehouse_schema=report.schema,
        created=report.created,
        skipped=report.skipped,
        errors=report.errors,
        ok=report.ok,
    )


@router.put(
    "/custom-reports/definitions/{report_id}",
    response_model=CustomReportDefinitionOut,
)
def update_custom_report_definition(
    report_id: int,
    payload: CustomReportDefinitionUpdate,
    ctx: TenantContext = Depends(get_current_tenant),
    _: str = Depends(verify_api_key),
    db: Session = Depends(get_db),
):
    try:
        return custom_reports_admin.update_definition(
            db, ctx.tenant_id, report_id, payload
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete(
    "/custom-reports/definitions/{report_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_custom_report_definition(
    report_id: int,
    ctx: TenantContext = Depends(get_current_tenant),
    _: str = Depends(verify_api_key),
    db: Session = Depends(get_db),
):
    try:
        custom_reports_admin.delete_definition(db, ctx.tenant_id, report_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/custom-reports/{view_name}/column-filters")
def column_filters(
    view_name: str,
    column: str | None = None,
    ctx: TenantContext = Depends(get_current_tenant),
    _: str = Depends(verify_api_key),
):
    try:
        return custom_reports_data.list_column_filter_options(
            _pg(ctx.tenant_id), ctx.tenant_id, view_name, column=column
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/custom-reports/{view_name}/payslip-filters")
def payslip_filters(
    view_name: str,
    ctx: TenantContext = Depends(get_current_tenant),
    _: str = Depends(verify_api_key),
):
    try:
        return custom_reports_data.list_payslip_filters(
            _pg(ctx.tenant_id), ctx.tenant_id, view_name
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/custom-reports/{view_name}/preview")
def preview_custom_report(
    view_name: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    emp_no: str | None = None,
    proc_year: int | None = None,
    proc_month: int | None = None,
    column_filters: str | None = None,
    ctx: TenantContext = Depends(get_current_tenant),
    _: str = Depends(verify_api_key),
):
    try:
        if custom_reports_data.is_payslip_view(view_name, ctx.tenant_id):
            if not emp_no or proc_year is None or proc_month is None:
                raise HTTPException(
                    status_code=400,
                    detail="Payslip preview requires emp_no, proc_year, and proc_month",
                )
            return custom_reports_data.preview_payslip(
                _pg(ctx.tenant_id),
                ctx.tenant_id,
                view_name,
                emp_no=emp_no,
                proc_year=proc_year,
                proc_month=proc_month,
            )
        return custom_reports_data.preview_view_data(
            _pg(ctx.tenant_id),
            ctx.tenant_id,
            view_name,
            limit=limit,
            offset=offset,
            filters=_export_filters(proc_year, proc_month, None, column_filters),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/custom-reports/{view_name}/export")
def export_custom_report(
    view_name: str,
    export_format: Literal["xlsx", "pdf"] = Query("xlsx"),
    proc_year: int | None = None,
    proc_month: int | None = None,
    emp_no: str | None = None,
    column_filters: str | None = None,
    ctx: TenantContext = Depends(get_current_tenant),
    _: str = Depends(verify_api_key),
):
    try:
        content, filename = custom_reports_data.export_view(
            _pg(ctx.tenant_id),
            ctx.tenant_id,
            view_name,
            export_format,
            filters=_export_filters(proc_year, proc_month, emp_no, column_filters),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return StreamingResponse(
        io.BytesIO(content),
        media_type=_EXPORT_MEDIA_TYPES[export_format],
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
