"""Employment mart API — workforce, salary bands, employee list."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.core.security import get_current_tenant, verify_api_key
from app.schemas.auth import TenantContext
from app.schemas.hr_metrics import EmployeeListResponse, EmploymentSummary
from app.services.hr_etl import employment_data

router = APIRouter()


def _pg(tenant_id: str):
    from app.core.warehouse import get_warehouse_engine_sync

    return get_warehouse_engine_sync(tenant_id)


@router.get("/employment/periods")
def get_available_periods(
    ctx: TenantContext = Depends(get_current_tenant),
    _: str = Depends(verify_api_key),
):
    tenant_id = ctx.tenant_id
    pg = _pg(ctx.tenant_id)
    periods = employment_data.list_available_periods(pg, tenant_id)
    default = employment_data.default_period(pg, tenant_id)
    return {
        "tenant_id": tenant_id,
        "default_period": default,
        "periods": periods,
        "marts_ready": employment_data.marts_ready(pg, tenant_id),
    }


@router.get("/employment/summary", response_model=EmploymentSummary)
def get_employment_summary(
    period_label: Optional[str] = Query(None, description="YYYY-MM"),
    ctx: TenantContext = Depends(get_current_tenant),
    _: str = Depends(verify_api_key),
):
    return employment_data.fetch_employment_summary(
        _pg(ctx.tenant_id), ctx.tenant_id, period_label=period_label
    )


@router.get("/employment/headcount-monthly")
def get_headcount_monthly(
    limit: int = Query(12, ge=1, le=36),
    period_label: Optional[str] = Query(None, description="YYYY-MM — if set, returns that month only"),
    ctx: TenantContext = Depends(get_current_tenant),
    _: str = Depends(verify_api_key),
):
    return {
        "tenant_id": ctx.tenant_id,
        "period_label": period_label,
        "items": employment_data.fetch_headcount_monthly(
            _pg(ctx.tenant_id), ctx.tenant_id, limit=limit, period_label=period_label
        ),
    }


@router.get("/employment/salary-bands")
def get_salary_bands(
    limit: int = Query(50, ge=1, le=200),
    period_label: Optional[str] = Query(None, description="YYYY-MM month-end snapshot"),
    ctx: TenantContext = Depends(get_current_tenant),
    _: str = Depends(verify_api_key),
):
    return {
        "tenant_id": ctx.tenant_id,
        "period_label": period_label,
        "items": employment_data.fetch_salary_bands(
            _pg(ctx.tenant_id), ctx.tenant_id, limit=limit, period_label=period_label
        ),
    }


@router.get("/employment/employees", response_model=EmployeeListResponse)
def get_employees(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    period_label: Optional[str] = Query(None, description="YYYY-MM — month-end roster"),
    ctx: TenantContext = Depends(get_current_tenant),
    _: str = Depends(verify_api_key),
):
    items, total = employment_data.fetch_employees(
        _pg(ctx.tenant_id), ctx.tenant_id, limit=limit, offset=offset, period_label=period_label
    )
    return EmployeeListResponse(
        tenant_id=ctx.tenant_id, total=total, limit=limit, offset=offset, items=items
    )


@router.get("/employment/lifecycle")
def get_lifecycle_summary(
    period_label: Optional[str] = Query(None),
    ctx: TenantContext = Depends(get_current_tenant),
    _: str = Depends(verify_api_key),
):
    pg = _pg(ctx.tenant_id)
    effective = period_label or employment_data.default_period(pg, ctx.tenant_id)
    return {
        "tenant_id": ctx.tenant_id,
        "period_label": effective,
        "items": employment_data.fetch_lifecycle_by_category(
            pg, ctx.tenant_id, period_label=effective
        ),
    }


@router.get("/employment/attendance-monthly")
def get_attendance_monthly(
    period_label: Optional[str] = Query(None),
    ctx: TenantContext = Depends(get_current_tenant),
    _: str = Depends(verify_api_key),
):
    pg = _pg(ctx.tenant_id)
    effective = period_label or employment_data.default_period(pg, ctx.tenant_id)
    result = employment_data.fetch_attendance_monthly_totals(
        pg, ctx.tenant_id, period_label=effective
    )
    result["period_label"] = effective
    return result
