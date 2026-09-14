"""HR Metric API routes.

Mirrors finance_metrics.py pattern.
All queries go through the semantic layer — never raw data.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.security import get_current_tenant, verify_api_key
from app.schemas.auth import TenantContext
from app.schemas.hr_metrics import (
    AttendanceSummary,
    HeadcountSummary,
    LeaveSummary,
    MetricResponse,
    PayrollSummary,
    PerformanceSummary,
)
from app.services.hr_etl import employment_data, payroll_data

router = APIRouter()
logger = logging.getLogger("hr_metrics.routes")


def _get_pg_engine(tenant_id: str):
    from app.core.warehouse import get_warehouse_engine_sync

    return get_warehouse_engine_sync(tenant_id)


# ── Helpers ──────────────────────────────────────────────────────────

def _latest_payroll_period(tenant_id: str) -> Optional[str]:
    """Most recent processed payroll month in the semantic layer."""
    try:
        from app.services.hr_etl.schema_names import semantic_schema

        pg = _get_pg_engine(tenant_id)
        semantic = semantic_schema(tenant_id)
        with pg.connect() as conn:
            from sqlalchemy import text
            return conn.execute(
                text(
                    f'SELECT period_label FROM "{semantic}".vw_payroll_summary'
                    " WHERE period_label IS NOT NULL"
                    " ORDER BY period_label DESC LIMIT 1"
                )
            ).scalar()
    except Exception as exc:
        logger.warning("latest payroll period lookup failed: %s", exc)
        return None


def _resolve(
    tenant_id: str,
    metric_name: str,
    period_label: Optional[str] = None,
    department_id: Optional[int] = None,
    branch_id: Optional[int] = None,
) -> Optional[float]:
    from app.services.hr_etl.metrics import HrMetricResolver
    try:
        pg = _get_pg_engine(tenant_id)
        resolver = HrMetricResolver(pg=pg, tenant_id=tenant_id)
        result = resolver.resolve(
            metric_name,
            period_label=period_label,
            department_id=department_id,
            branch_id=branch_id,
        )
        return result.value if result else None
    except Exception as exc:
        logger.warning(
            "Metric %s for tenant %s failed: %s", metric_name, tenant_id, exc
        )
        return None


# ── Endpoints ────────────────────────────────────────────────────────

@router.get("/metrics", response_model=List[Dict[str, Any]])
def list_metrics(
    ctx: TenantContext = Depends(get_current_tenant),
    _: str = Depends(verify_api_key),
):
    """List all available HR metrics."""
    from app.services.hr_etl.metrics import registry
    return [
        {
            "name":         m.name,
            "display_name": m.display_name,
            "description":  m.description,
            "unit":         m.unit,
            "category":     m.category,
            "rankable":     m.is_rankable,
            "aliases":      m.aliases,
        }
        for m in registry().all()
    ]


@router.get("/metric/{metric_name}", response_model=MetricResponse)
def get_metric(
    metric_name: str,
    period_label: Optional[str] = Query(None),
    department_id: Optional[int] = Query(None),
    branch_id: Optional[int] = Query(None),
    ctx: TenantContext = Depends(get_current_tenant),
    _: str = Depends(verify_api_key),
):
    """Resolve a single HR metric."""
    from app.services.hr_etl.metrics import HrMetricResolver, registry
    mdef = registry().get(metric_name)
    if not mdef:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Metric '{metric_name}' not found",
        )
    pg = _get_pg_engine(ctx.tenant_id)
    resolver = HrMetricResolver(pg=pg, tenant_id=ctx.tenant_id)
    result = resolver.resolve(
        metric_name,
        period_label=period_label,
        department_id=department_id,
        branch_id=branch_id,
    )
    if not result:
        raise HTTPException(status_code=500, detail="Metric resolution failed")
    return MetricResponse(
        name=result.name,
        display_name=result.display_name,
        unit=result.unit,
        value=result.value,
        period_label=result.period_label,
        department_id=result.department_id,
        branch_id=result.branch_id,
        derivation=result.derivation,
        components=result.components,
    )


@router.get("/headcount", response_model=HeadcountSummary)
def get_headcount_summary(
    period_label: Optional[str] = Query(None),
    department_id: Optional[int] = Query(None),
    branch_id: Optional[int] = Query(None),
    ctx: TenantContext = Depends(get_current_tenant),
    _: str = Depends(verify_api_key),
):
    """Headcount + turnover summary."""
    tenant_id = ctx.tenant_id
    # Active headcount is a point-in-time snapshot; movement metrics use payroll period.
    movement_period = (
        period_label
        or employment_data.latest_attendance_period(_get_pg_engine(tenant_id), tenant_id)
        or _latest_payroll_period(tenant_id)
    )
    total_hc = _resolve(tenant_id, "total_headcount", None, department_id, branch_id)
    separations = _resolve(tenant_id, "separations", movement_period, department_id, branch_id)
    turnover_rate: Optional[float] = None
    if total_hc and total_hc > 0 and separations is not None:
        turnover_rate = separations / total_hc * 100.0

    return HeadcountSummary(
        tenant_id=tenant_id,
        period_label=movement_period,
        total_headcount=total_hc,
        new_hires=_resolve(tenant_id, "new_hires", movement_period, department_id, branch_id),
        separations=separations,
        turnover_rate=turnover_rate,
    )


@router.get("/payroll", response_model=PayrollSummary)
def get_payroll_summary(
    period_label: Optional[str] = Query(None),
    department_id: Optional[int] = Query(None),
    branch_id: Optional[int] = Query(None),
    ctx: TenantContext = Depends(get_current_tenant),
    _: str = Depends(verify_api_key),
):
    """Payroll cost summary (processed payroll marts)."""
    tenant_id = ctx.tenant_id
    summary = payroll_data.fetch_payroll_summary(
        _get_pg_engine(tenant_id), tenant_id, period_label=period_label
    )
    additions = summary.get("total_additions")
    return PayrollSummary(
        tenant_id=tenant_id,
        period_label=summary.get("period_label"),
        payroll_employee_count=summary.get("payroll_employee_count"),
        total_payroll_cost=summary.get("total_payroll_cost"),
        average_salary=summary.get("average_salary"),
        total_gross=summary.get("total_gross"),
        total_additions=additions,
        total_tax=summary.get("total_tax"),
        total_statutory=summary.get("total_statutory"),
        total_overtime_cost=additions,
    )


@router.get("/attendance", response_model=AttendanceSummary)
def get_attendance_summary(
    period_label: Optional[str] = Query(None),
    department_id: Optional[int] = Query(None),
    branch_id: Optional[int] = Query(None),
    ctx: TenantContext = Depends(get_current_tenant),
    _: str = Depends(verify_api_key),
):
    """Attendance summary."""
    tenant_id = ctx.tenant_id
    effective_period = period_label or employment_data.latest_attendance_period(
        _get_pg_engine(tenant_id), tenant_id
    )
    return AttendanceSummary(
        tenant_id=tenant_id,
        period_label=effective_period,
        attendance_rate=_resolve(tenant_id, "attendance_rate", effective_period, department_id, branch_id),
        late_arrivals=_resolve(tenant_id, "late_arrivals", effective_period, department_id, branch_id),
        total_overtime_hours=_resolve(tenant_id, "total_overtime_hours", effective_period, department_id, branch_id),
    )


@router.get("/leave", response_model=LeaveSummary)
def get_leave_summary(
    period_label: Optional[str] = Query(None),
    department_id: Optional[int] = Query(None),
    branch_id: Optional[int] = Query(None),
    ctx: TenantContext = Depends(get_current_tenant),
    _: str = Depends(verify_api_key),
):
    """Leave summary."""
    tenant_id = ctx.tenant_id
    return LeaveSummary(
        tenant_id=tenant_id,
        period_label=period_label,
        leave_days_taken=_resolve(tenant_id, "leave_days_taken", period_label, department_id, branch_id),
        leave_days_entitled=_resolve(tenant_id, "leave_days_entitled", period_label, department_id, branch_id),
        leave_utilization_rate=_resolve(tenant_id, "leave_utilization_rate", period_label, department_id, branch_id),
        sick_leave_days=_resolve(tenant_id, "sick_leave_days", period_label, department_id, branch_id),
    )


@router.get("/performance", response_model=PerformanceSummary)
def get_performance_summary(
    period_label: Optional[str] = Query(None),
    department_id: Optional[int] = Query(None),
    branch_id: Optional[int] = Query(None),
    ctx: TenantContext = Depends(get_current_tenant),
    _: str = Depends(verify_api_key),
):
    """Performance summary."""
    tenant_id = ctx.tenant_id
    return PerformanceSummary(
        tenant_id=tenant_id,
        period_label=period_label,
        average_performance_score=_resolve(tenant_id, "average_performance_score", period_label, department_id, branch_id),
        high_performers=_resolve(tenant_id, "high_performers", period_label, department_id, branch_id),
    )
