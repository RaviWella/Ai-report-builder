"""ETL source databases API — unified MySQL/PostgreSQL registration."""
from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db, get_tenant_db
from app.core.security import get_current_tenant, verify_api_key
from app.schemas.auth import TenantContext
from app.schemas.tenant import (
    SourceDatabaseCreate,
    SourceDatabaseOut,
    SourceDatabaseTest,
    TenantEtlSourceCreate,
    TenantEtlSourceOut,
)
from app.services import tenant_etl_sources as etl_src_svc
from app.services.database_connection import TenantQuotaExceeded
from app.services.etl_source_scenarios import classify_etl_sources
from app.services.source_databases import (
    create_source_database,
    delete_source_database,
    list_source_databases,
    test_source_database,
)

router = APIRouter()
logger = logging.getLogger("etl_sources")


def _view_to_out(view) -> SourceDatabaseOut:
    return SourceDatabaseOut(
        id=view.id,
        tenant_id=view.tenant_id,
        source_key=view.source_key,
        display_name=view.display_name,
        source_type=view.source_type,
        connection_id=view.connection_id,
        source_schema=view.source_schema,
        extractor_profile=view.extractor_profile,
        mapping_variant=view.mapping_variant,
        is_primary=view.is_primary,
        is_active=view.is_active,
        priority=view.priority,
        staging_suffix=view.staging_suffix,
        host=view.host,
        port=view.port,
        database_name=view.database_name,
        username=view.username,
        connection_name=view.connection_name,
        is_healthy=view.is_healthy,
    )


def _legacy_row_to_out(row: etl_src_svc.TenantEtlSourceRow) -> TenantEtlSourceOut:
    return TenantEtlSourceOut(
        id=row.id,
        tenant_id=row.tenant_id,
        source_key=row.source_key,
        display_name=row.display_name,
        source_type=row.source_type,
        connection_id=row.connection_id,
        source_schema=row.source_schema,
        extractor_profile=row.extractor_profile,
        mapping_variant=row.mapping_variant,
        is_primary=row.is_primary,
        is_active=row.is_active,
        priority=row.priority,
        staging_suffix=row.staging_suffix,
    )


@router.get("/scenario")
def etl_sources_scenario(
    ctx: TenantContext = Depends(get_current_tenant),
    _: str = Depends(verify_api_key),
    db: Session = Depends(get_db),
):
    rows = etl_src_svc.list_sources_for_api(db, ctx.tenant_id)
    return classify_etl_sources(rows)


@router.get("/", response_model=List[SourceDatabaseOut])
def list_etl_sources(
    ctx: TenantContext = Depends(get_current_tenant),
    _: str = Depends(verify_api_key),
    platform_db: Session = Depends(get_db),
    mart_db: Session = Depends(get_tenant_db),
):
    """List ETL source databases with connection details (single unified view)."""
    views = list_source_databases(platform_db, mart_db, ctx.tenant_id)
    return [_view_to_out(v) for v in views]


@router.post("/test")
def test_etl_source_connection(
    payload: SourceDatabaseTest,
    _: str = Depends(verify_api_key),
    __: TenantContext = Depends(get_current_tenant),
):
    """Test source DB connectivity (same code path as save)."""
    st = payload.source_type
    port = payload.port
    if port is None:
        port = 5432 if st == "postgres" else 3306
    result = test_source_database(
        {
            "display_name": "test",
            "source_key": "test",
            "source_type": st,
            "host": payload.host,
            "port": port,
            "database_name": payload.database_name,
            "username": payload.username,
            "password": payload.password,
            "source_schema": payload.source_schema,
        }
    )
    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("message", "Connection failed"),
        )
    return result


@router.post("/", response_model=SourceDatabaseOut, status_code=201)
def create_etl_source(
    payload: SourceDatabaseCreate,
    ctx: TenantContext = Depends(get_current_tenant),
    _: str = Depends(verify_api_key),
    platform_db: Session = Depends(get_db),
    mart_db: Session = Depends(get_tenant_db),
):
    """Register one ETL source database (credentials + ETL metadata in one step)."""
    if not (settings.DB_ENCRYPTION_KEY or "").strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "DB_ENCRYPTION_KEY is not set on the API server. "
                "Source credentials cannot be saved until this Fernet key is configured "
                '(generate: python -c "from cryptography.fernet import Fernet; '
                'print(Fernet.generate_key().decode())").'
            ),
        )

    port = payload.port
    if port is None:
        port = 5432 if payload.source_type == "postgres" else 3306
    try:
        view = create_source_database(
            platform_db,
            ctx.tenant_id,
            source_key=payload.source_key,
            display_name=payload.display_name,
            source_type=payload.source_type,
            host=payload.host,
            port=port,
            database_name=payload.database_name,
            username=payload.username,
            password=payload.password,
            source_schema=payload.source_schema,
            extractor_profile=payload.extractor_profile,
            mapping_variant=payload.mapping_variant,
            is_primary=payload.is_primary,
            priority=payload.priority,
            mart_db=mart_db,
        )
    except TenantQuotaExceeded as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except IntegrityError as exc:
        err = str(getattr(exc, "orig", exc))
        if "uq_tenant_etl_sources_key" in err or "duplicate key" in err.lower():
            detail = (
                f"ETL source '{payload.source_key.strip().lower()}' already exists "
                f"for tenant '{ctx.tenant_id}'. Delete it under Settings → Source "
                "Databases or use a different source key."
            )
        else:
            detail = "Database constraint violation while saving ETL source."
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail) from exc
    except ProgrammingError as exc:
        err = str(getattr(exc, "orig", exc))
        if "tenant_etl_sources" in err:
            detail = (
                "Platform migration missing: run alembic upgrade head on the "
                "application database (hrm_control.tenant_etl_sources)."
            )
        elif "database_connections" in err:
            detail = (
                "Tenant warehouse metadata tables are missing. Ensure the tenant "
                "warehouse database exists (WAREHOUSE_* / tenant_registry)."
            )
        else:
            detail = err if settings.DEBUG else "Database schema error while saving ETL source."
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=detail,
        ) from exc
    except OperationalError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Cannot reach the tenant analytics warehouse database. "
                "Check WAREHOUSE_* settings and that the warehouse DB exists. "
                f"({exc.orig})"
            ),
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("create_etl_source failed tenant=%s", ctx.tenant_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc) if settings.DEBUG else "Failed to create ETL source.",
        ) from exc
    return _view_to_out(view)


@router.post("/legacy", response_model=TenantEtlSourceOut, status_code=201, deprecated=True)
def create_etl_source_legacy(
    payload: TenantEtlSourceCreate,
    ctx: TenantContext = Depends(get_current_tenant),
    _: str = Depends(verify_api_key),
    db: Session = Depends(get_db),
):
    """Deprecated: use POST / with SourceDatabaseCreate instead."""
    if payload.source_type == "postgres" and not payload.source_schema:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="PostgreSQL sources require source_schema",
        )
    if not payload.connection_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="connection_id is required for legacy create; use POST / with full connection fields",
        )
    try:
        row = etl_src_svc.create_source(
            db,
            ctx.tenant_id,
            source_key=payload.source_key,
            display_name=payload.display_name,
            source_type=payload.source_type,
            connection_id=payload.connection_id,
            source_schema=payload.source_schema,
            extractor_profile=payload.extractor_profile,
            mapping_variant=payload.mapping_variant,
            is_primary=payload.is_primary,
            priority=payload.priority,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return _legacy_row_to_out(row)


@router.delete("/{source_id}", status_code=204)
def delete_etl_source(
    source_id: int,
    ctx: TenantContext = Depends(get_current_tenant),
    _: str = Depends(verify_api_key),
    platform_db: Session = Depends(get_db),
    mart_db: Session = Depends(get_tenant_db),
):
    if not delete_source_database(
        platform_db, mart_db, ctx.tenant_id, source_id, delete_connection=True
    ):
        raise HTTPException(status_code=404, detail="ETL source not found")
