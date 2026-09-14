"""Tenant management routes — register, list, and configure ETL source DB."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db, get_tenant_db
from app.core.security import get_current_tenant, verify_api_key
from app.schemas.auth import TenantContext
from app.schemas.tenant import (
    TenantCreate,
    TenantProvisionMinimal,
    TenantProvisionResponse,
    TenantResponse,
    TenantSourceConnectionSet,
    TenantSourceResponse,
    TenantSourceTest,
    TenantSourceUpdate,
)
from app.services import tenant_source as tenant_source_svc
from app.services.tenant_provision import provision_tenant_minimal
from app.services.hr_etl.source_connection import TenantSourceConfig, normalize_source_type

router = APIRouter()


def _row_to_source_response(tenant_id: str, row: dict | None) -> TenantSourceResponse:
    if not row:
        return TenantSourceResponse(
            tenant_id=tenant_id,
            configured=False,
            extractor_profile=settings.MYSQL_EXTRACTOR_PROFILE,
        )
    return TenantSourceResponse(
        tenant_id=row["tenant_id"],
        configured=True,
        display_name=row["display_name"],
        source_type=row["source_type"],
        mysql_host=row["mysql_host"],
        mysql_port=int(row["mysql_port"]) if row["mysql_port"] is not None else None,
        mysql_db=row["mysql_db"],
        mysql_user=row["mysql_user"],
        has_password=bool(row.get("mysql_password_enc")),
        is_active=bool(row.get("is_active", True)),
        last_etl_at=str(row["last_etl_at"]) if row.get("last_etl_at") else None,
        extractor_profile=settings.MYSQL_EXTRACTOR_PROFILE,
        source_connection_id=row.get("source_connection_id"),
        source_connection_name=row.get("source_connection_name"),
        source_connection_engine=row.get("source_connection_engine"),
    )


# ── ETL source (current tenant) — must be before /{tenant_id} if added ──

@router.get("/source", response_model=TenantSourceResponse)
def get_tenant_source(
    ctx: TenantContext = Depends(get_current_tenant),
    _: str = Depends(verify_api_key),
    platform_db: Session = Depends(get_db),
    mart_db: Session = Depends(get_tenant_db),
):
    """Summary of ETL source DBs (primary source). Prefer GET /tenants/etl-sources/."""
    from app.services.source_databases import list_source_databases

    views = list_source_databases(platform_db, mart_db, ctx.tenant_id)
    if views:
        primary = next((v for v in views if v.is_primary), views[0])
        return TenantSourceResponse(
            tenant_id=ctx.tenant_id,
            configured=True,
            display_name=primary.display_name,
            source_type=primary.source_type,
            mysql_host=primary.host,
            mysql_port=primary.port,
            mysql_db=primary.database_name,
            mysql_user=primary.username,
            has_password=True,
            is_active=primary.is_active,
            extractor_profile=primary.extractor_profile,
            source_connection_id=primary.connection_id,
            source_connection_name=primary.connection_name,
            source_connection_engine=primary.source_type,
        )
    row = tenant_source_svc.get_tenant_source_with_connection(platform_db, ctx.tenant_id)
    return _row_to_source_response(ctx.tenant_id, row)


@router.put("/source/connection", response_model=TenantSourceResponse, deprecated=True)
def set_source_connection(
    payload: TenantSourceConnectionSet,
    ctx: TenantContext = Depends(get_current_tenant),
    _: str = Depends(verify_api_key),
    platform_db: Session = Depends(get_db),
    mart_db: Session = Depends(get_tenant_db),
):
    """Deprecated: add sources via POST /tenants/etl-sources/ instead."""
    from app.services.database_connection import DatabaseConnectionService
    from app.services.source_databases import sync_tenant_registry_primary

    if payload.connection_id is not None:
        conn = DatabaseConnectionService(mart_db).get_connection(payload.connection_id)
        if not conn or not conn.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"DatabaseConnection id={payload.connection_id} not found in tenant warehouse",
            )
    try:
        row = tenant_source_svc.set_source_connection_id(
            platform_db, ctx.tenant_id, payload.connection_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    sync_tenant_registry_primary(platform_db, ctx.tenant_id)
    return _row_to_source_response(ctx.tenant_id, row)


@router.put("/source", response_model=TenantSourceResponse, deprecated=True)
def upsert_tenant_source(
    payload: TenantSourceUpdate,
    ctx: TenantContext = Depends(get_current_tenant),
    _: str = Depends(verify_api_key),
    platform_db: Session = Depends(get_db),
    mart_db: Session = Depends(get_tenant_db),
):
    """Deprecated: use POST /tenants/etl-sources/ (unified source database API)."""
    try:
        row = tenant_source_svc.upsert_tenant_source(
            platform_db,
            ctx.tenant_id,
            display_name=payload.display_name,
            source_type=payload.source_type,
            mysql_host=payload.mysql_host,
            mysql_port=payload.mysql_port,
            mysql_db=payload.mysql_db,
            mysql_user=payload.mysql_user,
            mysql_password=payload.mysql_password,
        )
        from app.services.source_databases import sync_tenant_registry_primary

        sync_tenant_registry_primary(platform_db, ctx.tenant_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save source connection: {exc}",
        )
    return _row_to_source_response(ctx.tenant_id, row)


@router.post("/source/test", deprecated=True)
def test_tenant_source(
    payload: TenantSourceTest,
    ctx: TenantContext = Depends(get_current_tenant),
    _: str = Depends(verify_api_key),
):
    """Deprecated: use POST /tenants/etl-sources/test instead."""
    from app.services.source_databases import test_source_database

    st = normalize_source_type(payload.source_type)
    port = payload.mysql_port
    if port is None:
        port = 5432 if st == "postgres" else 3306
    result = test_source_database(
        {
            "display_name": "test",
            "source_key": "test",
            "source_type": st,
            "host": payload.mysql_host,
            "port": port,
            "database_name": payload.mysql_db,
            "username": payload.mysql_user,
            "password": payload.mysql_password,
        }
    )
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["message"],
        )
    return result


@router.post(
    "/provision-minimal",
    response_model=TenantProvisionResponse,
    status_code=status.HTTP_201_CREATED,
)
def provision_tenant_minimal_route(
    payload: TenantProvisionMinimal,
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """
    Register tenant identity + warehouse routing only (HRIS / ops onboarding).

    Customer **source** DB credentials belong in Settings → Source Databases
    (``tenant_etl_sources`` + per-tenant ``database_connections``), not here.
    """
    from app.core.warehouse import default_warehouse_db_name, ensure_warehouse_ready_sync, get_warehouse_engine_sync
    from app.core.tenant import invalidate_warehouse_layers_ready

    tid = payload.tenant_id.strip()
    if not tid:
        raise HTTPException(status_code=400, detail="tenant_id is required")

    try:
        created = provision_tenant_minimal(
            db,
            tid,
            display_name=payload.display_name,
            warehouse_db=payload.warehouse_db,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to provision tenant: {exc}",
        ) from exc

    whdb = (payload.warehouse_db or "").strip() or default_warehouse_db_name(tid)
    invalidate_warehouse_layers_ready(tid)
    try:
        wh = get_warehouse_engine_sync(tid, provision=True)
        try:
            ensure_warehouse_ready_sync(wh, tid)
        finally:
            wh.dispose()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Tenant registered but warehouse setup failed: {exc}",
        ) from exc

    return TenantProvisionResponse(
        tenant_id=tid,
        display_name=(payload.display_name or tid).strip(),
        warehouse_db=whdb,
        created=created,
        message=(
            "Tenant provisioned. Add source databases under Settings → Source Databases."
            if created
            else "Tenant reactivated. Source DBs remain in tenant_etl_sources / UI."
        ),
    )


@router.post("/", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
def register_tenant(
    payload: TenantCreate,
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """Register a new customer tenant (identity + warehouse only).

    mysql_* fields in the body are **ignored**. Add source databases after login via
    Settings → Source Databases (``tenant_etl_sources``). Prefer POST /provision-minimal.
    """
    from app.core.tenant import invalidate_warehouse_layers_ready
    from app.core.warehouse import default_warehouse_db_name, ensure_warehouse_ready_sync, get_warehouse_engine_sync

    tid = payload.tenant_id.strip()
    try:
        provision_tenant_minimal(db, tid, display_name=payload.display_name)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Tenant already exists or DB error: {exc}",
        ) from exc

    invalidate_warehouse_layers_ready(tid)
    wh = get_warehouse_engine_sync(tid, provision=True)
    try:
        ensure_warehouse_ready_sync(wh, tid)
    finally:
        wh.dispose()

    return TenantResponse(
        tenant_id=tid,
        display_name=payload.display_name,
        is_active=True,
    )


@router.get("/", response_model=List[TenantResponse])
def list_tenants(
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """List all registered tenants."""
    result = db.execute(
        text(
            "SELECT tenant_id, display_name, COALESCE(source_type, 'mysql') AS source_type,"
            "       mysql_host, mysql_port, mysql_db, is_active, last_etl_at"
            " FROM hrm_control.tenant_registry"
            " ORDER BY tenant_id"
        )
    )
    rows = result.mappings().all()
    return [
        TenantResponse(
            tenant_id=r["tenant_id"],
            display_name=r["display_name"],
            source_type=r["source_type"],
            mysql_host=r.get("mysql_host"),
            mysql_port=r.get("mysql_port"),
            mysql_db=r.get("mysql_db"),
            is_active=r["is_active"],
            last_etl_at=str(r["last_etl_at"]) if r["last_etl_at"] else None,
        )
        for r in rows
    ]
