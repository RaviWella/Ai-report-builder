"""HR ETL routes — trigger and monitor ETL runs per tenant."""
from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import get_warehouse_db
from app.core.security import get_current_tenant, verify_api_key
from app.core.warehouse import ensure_warehouse_ready_sync, get_platform_engine_sync, get_warehouse_engine_sync
from app.schemas.auth import TenantContext
from app.schemas.hr_metrics import EtlRunRequest
from app.services.hr_etl import control
from app.services.hr_etl.errors import format_run_error, run_error_payload
from app.services.hr_etl.multi_source_runner import run_tenant_etl
from app.services.hr_etl.preflight import preflight_etl_sources
from app.services.hr_etl.schema_names import control_schema

router = APIRouter()
logger = logging.getLogger("hr_etl.routes")


def _run_etl_background(tenant_id: str, run_type: str, triggered_by: str, run_id: int):
    try:
        incremental = run_type == "incremental"
        result = run_tenant_etl(
            tenant_id,
            run_type,
            triggered_by,
            incremental=incremental,
            run_id=run_id,
        )
        logger.info("ETL background task completed: %s", result)
    except Exception as exc:
        logger.exception(
            "ETL background task failed tenant=%s run_id=%s: %s",
            tenant_id,
            run_id,
            exc,
        )
        try:
            pg = get_warehouse_engine_sync(tenant_id)
            control.fail_run(
                pg, tenant_id, run_id, format_run_error(exc), exc=exc
            )
        except Exception:
            logger.exception("Failed to mark ETL run %s as failed", run_id)


@router.post("/run")
def trigger_etl_run(
    body: EtlRunRequest,
    background_tasks: BackgroundTasks,
    ctx: TenantContext = Depends(get_current_tenant),
    _: str = Depends(verify_api_key),
):
    if body.run_type not in ("full_load", "incremental"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="run_type must be 'full_load' or 'incremental'",
        )

    platform = get_platform_engine_sync()
    preflight_errors = preflight_etl_sources(platform, ctx.tenant_id)
    if preflight_errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": (
                    "ETL preflight failed — fix source configuration before running."
                ),
                "errors": preflight_errors,
            },
        )

    warehouse = get_warehouse_engine_sync(ctx.tenant_id)
    ensure_warehouse_ready_sync(warehouse, ctx.tenant_id)
    run_id = control.start_run(
        warehouse, ctx.tenant_id, body.run_type, body.triggered_by
    )
    logger.info(
        "ETL run queued tenant=%s run_id=%s type=%s triggered_by=%s",
        ctx.tenant_id,
        run_id,
        body.run_type,
        body.triggered_by,
    )

    background_tasks.add_task(
        _run_etl_background, ctx.tenant_id, body.run_type, body.triggered_by, run_id
    )
    return {
        "status": "accepted",
        "run_status": "running",
        "tenant_id": ctx.tenant_id,
        "run_id": run_id,
        "run_type": body.run_type,
        "message": "ETL run started in background",
        "status_url": f"/api/v1/hr-etl/status?run_id={run_id}",
    }


@router.get("/status")
def get_etl_status(
    ctx: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_warehouse_db),
    _: str = Depends(verify_api_key),
    limit: int = 20,
) -> Dict[str, Any]:
    schema = ctx.control_schema
    result = db.execute(
        text(
            f"""
            SELECT run_id, run_type, status, started_at, completed_at,
                   rows_extracted, rows_loaded, error_message, triggered_by
            FROM "{schema}".hr_etl_run_log
            ORDER BY started_at DESC
            LIMIT :lim
            """
        ),
        {"lim": max(1, min(limit, 100))},
    )
    runs = [dict(r) for r in result.mappings().all()]
    for run in runs:
        if run.get("status") == "failed":
            msg = (run.get("error_message") or "").strip()
            if msg:
                run["error"] = run_error_payload(msg)
            else:
                run["error"] = run_error_payload(
                    "ETL failed with no error message recorded.",
                    error_code="ETL_RUN_FAILED_EMPTY",
                )
    if not runs:
        return {"tenant_id": ctx.tenant_id, "status": "no_runs", "runs": []}
    latest = runs[0]
    payload: Dict[str, Any] = {
        "tenant_id": ctx.tenant_id,
        "status": latest.get("status"),
        "runs": runs,
        **{k: latest[k] for k in latest if k not in ("status", "error")},
    }
    if latest.get("status") == "failed" and latest.get("error"):
        payload["error"] = latest["error"]
    return payload


@router.post("/runs/clear-stuck")
def clear_stuck_runs(
    ctx: TenantContext = Depends(get_current_tenant),
    _: str = Depends(verify_api_key),
    max_age_hours: int = 2,
) -> Dict[str, Any]:
    """Mark long-running ETL rows as failed (e.g. after API reload killed the worker)."""
    warehouse = get_warehouse_engine_sync(ctx.tenant_id)
    schema = ctx.control_schema
    hours = max(1, min(max_age_hours, 168))
    with warehouse.begin() as conn:
        rows = conn.execute(
            text(
                f"""
                UPDATE "{schema}".hr_etl_run_log
                SET status = 'failed',
                    completed_at = NOW(),
                    error_message = COALESCE(
                        NULLIF(error_message, ''),
                        'Run interrupted or timed out (marked stale). '
                        'If you stopped the API server, use Clear stuck runs and retry.'
                    )
                WHERE status = 'running'
                  AND started_at < NOW() - CAST(:hours AS integer) * interval '1 hour'
                RETURNING run_id
                """
            ),
            {"hours": hours},
        ).fetchall()
    cleared = [int(r[0]) for r in rows]
    return {"tenant_id": ctx.tenant_id, "cleared_run_ids": cleared, "count": len(cleared)}


@router.get("/watermarks")
def get_watermarks(
    ctx: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_warehouse_db),
    _: str = Depends(verify_api_key),
) -> Dict[str, Any]:
    schema = ctx.control_schema
    result = db.execute(
        text(
            f"""
            SELECT table_name, last_value, rows_at_mark, updated_at
            FROM "{schema}".hr_etl_watermark
            ORDER BY table_name
            """
        )
    )
    rows = result.mappings().all()
    return {"tenant_id": ctx.tenant_id, "watermarks": [dict(r) for r in rows]}
