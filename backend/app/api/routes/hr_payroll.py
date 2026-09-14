"""Payroll mart API — processed payroll register, compliance, components."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.core.security import get_current_tenant, verify_api_key
from app.schemas.auth import TenantContext
from app.schemas.hr_metrics import PayrollMartSummary, PayrollRegisterResponse
from app.services.hr_etl import payroll_data

router = APIRouter()


def _pg(tenant_id: str):
    from app.core.warehouse import get_warehouse_engine_sync

    return get_warehouse_engine_sync(tenant_id)


@router.get("/payroll/summary", response_model=PayrollMartSummary)
def get_payroll_mart_summary(
    period_label: Optional[str] = Query(None, description="YYYY-MM"),
    ctx: TenantContext = Depends(get_current_tenant),
    _: str = Depends(verify_api_key),
):
    return payroll_data.fetch_payroll_summary(
        _pg(ctx.tenant_id), ctx.tenant_id, period_label=period_label
    )


@router.get("/payroll/register", response_model=PayrollRegisterResponse)
def get_payroll_register(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    period_label: Optional[str] = Query(None, description="YYYY-MM"),
    ctx: TenantContext = Depends(get_current_tenant),
    _: str = Depends(verify_api_key),
):
    items, total = payroll_data.fetch_payroll_register(
        _pg(ctx.tenant_id), ctx.tenant_id, limit=limit, offset=offset, period_label=period_label
    )
    effective = period_label or payroll_data.fetch_payroll_summary(
        _pg(ctx.tenant_id), ctx.tenant_id
    ).get("period_label")
    return PayrollRegisterResponse(
        tenant_id=ctx.tenant_id,
        period_label=effective,
        total=total,
        limit=limit,
        offset=offset,
        items=items,
    )


@router.get("/payroll/compliance")
def get_payroll_compliance(
    period_label: Optional[str] = Query(None),
    ctx: TenantContext = Depends(get_current_tenant),
    _: str = Depends(verify_api_key),
):
    items = payroll_data.fetch_payroll_compliance(
        _pg(ctx.tenant_id), ctx.tenant_id, period_label=period_label
    )
    summary = payroll_data.fetch_payroll_summary(
        _pg(ctx.tenant_id), ctx.tenant_id, period_label=period_label
    )
    return {
        "tenant_id": ctx.tenant_id,
        "period_label": summary.get("period_label"),
        "items": items,
    }


@router.get("/payroll/components")
def get_payroll_components(
    period_label: Optional[str] = Query(None),
    limit: int = Query(25, ge=1, le=100),
    ctx: TenantContext = Depends(get_current_tenant),
    _: str = Depends(verify_api_key),
):
    summary = payroll_data.fetch_payroll_summary(
        _pg(ctx.tenant_id), ctx.tenant_id, period_label=period_label
    )
    return {
        "tenant_id": ctx.tenant_id,
        "period_label": summary.get("period_label"),
        "items": payroll_data.fetch_payroll_components(
            _pg(ctx.tenant_id), ctx.tenant_id, period_label=period_label, limit=limit
        ),
    }
