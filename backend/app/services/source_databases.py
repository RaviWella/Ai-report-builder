"""ETL source database configuration — management DB only.

Standard layout (application / hrm_control schema):
  - ``tenant_registry``: tenant identity + analytics warehouse routing (onboarding)
  - ``tenant_etl_sources``: customer source DB credentials + ETL metadata (UI after login)

Legacy: ``connection_id`` may point at per-tenant warehouse ``database_connections``;
new saves store credentials inline on ``tenant_etl_sources``.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.warehouse import get_layout_sync, get_platform_engine_sync, get_warehouse_engine_sync
from app.services.database_connection import (
    DatabaseConnectionService,
    TenantQuotaExceeded,
    encrypt_password,
)
from app.services.hr_etl.source_connection import (
    TenantSourceConfig,
    _load_from_database_connection,
    build_source_engine,
    config_from_etl_source_row,
    normalize_source_type,
)
from app.services import tenant_etl_sources as etl_src
from app.services import tenant_source as tenant_src

logger = logging.getLogger("source_databases")


@dataclass(frozen=True)
class SourceDatabaseView:
    """API-facing view: ETL source row + non-secret connection fields."""

    id: int
    tenant_id: str
    source_key: str
    display_name: str
    source_type: str
    connection_id: int
    source_schema: Optional[str]
    extractor_profile: str
    mapping_variant: Optional[str]
    is_primary: bool
    is_active: bool
    priority: int
    staging_suffix: str
    host: str
    port: int
    database_name: str
    username: str
    connection_name: str
    is_healthy: bool = True


def _connection_payload_from_form(
    *,
    display_name: str,
    source_key: str,
    source_type: str,
    host: str,
    port: int,
    database_name: str,
    username: str,
    password: str,
    source_schema: Optional[str] = None,
) -> dict[str, Any]:
    engine = "postgres" if normalize_source_type(source_type) == "postgres" else "mysql"
    return {
        "name": f"{display_name.strip()} ({source_key.strip()})",
        "engine": engine,
        "host": host.strip(),
        "port": int(port),
        "database_name": database_name.strip(),
        "username": username.strip(),
        "password": password,
        "default_schema": (source_schema or "").strip() or None,
    }


def _view_from_row(row: etl_src.TenantEtlSourceRow) -> Optional[SourceDatabaseView]:
    if row.has_control_plane_credentials():
        return SourceDatabaseView(
            id=row.id,
            tenant_id=row.tenant_id,
            source_key=row.source_key,
            display_name=row.display_name,
            source_type=row.source_type,
            connection_id=int(row.connection_id or 0),
            source_schema=row.source_schema,
            extractor_profile=row.extractor_profile,
            mapping_variant=row.mapping_variant,
            is_primary=row.is_primary,
            is_active=row.is_active,
            priority=row.priority,
            staging_suffix=row.staging_suffix,
            host=str(row.host),
            port=int(row.port or (5432 if row.source_type == "postgres" else 3306)),
            database_name=str(row.database_name),
            username=str(row.username),
            connection_name=row.display_name,
            is_healthy=True,
        )
    return None


def _row_to_view(
    platform_db: Session,
    mart_db: Optional[Session],
    row: etl_src.TenantEtlSourceRow,
) -> Optional[SourceDatabaseView]:
    inline = _view_from_row(row)
    if inline:
        return inline
    if row.connection_id and mart_db is not None:
        svc = DatabaseConnectionService(mart_db)
        conn = svc.get_connection(int(row.connection_id))
        if conn and conn.is_active:
            return SourceDatabaseView(
                id=row.id,
                tenant_id=row.tenant_id,
                source_key=row.source_key,
                display_name=row.display_name,
                source_type=row.source_type,
                connection_id=int(row.connection_id),
                source_schema=row.source_schema,
                extractor_profile=row.extractor_profile,
                mapping_variant=row.mapping_variant,
                is_primary=row.is_primary,
                is_active=row.is_active,
                priority=row.priority,
                staging_suffix=row.staging_suffix,
                host=conn.host,
                port=int(conn.port),
                database_name=conn.database_name,
                username=conn.username,
                connection_name=conn.name,
                is_healthy=bool(conn.is_healthy),
            )
    return None


def list_source_databases(
    platform_db: Session,
    mart_db: Optional[Session],
    tenant_id: str,
) -> list[SourceDatabaseView]:
    rows = etl_src.list_sources_for_api(platform_db, tenant_id)
    views: list[SourceDatabaseView] = []
    for row in rows:
        if row.id == 0:
            reg = tenant_src.get_tenant_source(platform_db, tenant_id)
            if reg and (reg.get("mysql_host") or reg.get("source_connection_id")):
                views.append(
                    SourceDatabaseView(
                        id=0,
                        tenant_id=tenant_id,
                        source_key=row.source_key,
                        display_name=row.display_name,
                        source_type=normalize_source_type(reg.get("source_type")),
                        connection_id=int(reg.get("source_connection_id") or 0),
                        source_schema=None,
                        extractor_profile=row.extractor_profile,
                        mapping_variant=None,
                        is_primary=True,
                        is_active=True,
                        priority=0,
                        staging_suffix="",
                        host=reg.get("mysql_host") or "",
                        port=int(reg.get("mysql_port") or 3306),
                        database_name=reg.get("mysql_db") or "",
                        username=reg.get("mysql_user") or "",
                        connection_name="Legacy (tenant registry)",
                        is_healthy=True,
                    )
                )
            continue
        view = _row_to_view(platform_db, mart_db, row)
        if view:
            views.append(view)
    return views


def test_source_database(data: dict[str, Any]) -> dict[str, Any]:
    """Test connectivity using the same path as saved connections."""
    svc = DatabaseConnectionService(None)  # type: ignore[arg-type]
    return svc.test_connection(_connection_payload_from_form(**data))


def create_source_database(
    platform_db: Session,
    tenant_id: str,
    *,
    source_key: str,
    display_name: str,
    source_type: str,
    host: str,
    port: int,
    database_name: str,
    username: str,
    password: str,
    source_schema: Optional[str] = None,
    extractor_profile: str = "minthrm",
    mapping_variant: Optional[str] = None,
    is_primary: bool = False,
    priority: int = 0,
    mart_db: Optional[Session] = None,
) -> SourceDatabaseView:
    """Save source DB in hrm_control.tenant_etl_sources (management DB)."""
    st = normalize_source_type(source_type)
    if st == "postgres" and not (source_schema or "").strip():
        raise ValueError(
            "PostgreSQL sources require source_schema (customer schema in the database)"
        )

    key = etl_src.normalize_source_key(source_key)
    existing = etl_src.find_source_by_key(platform_db, tenant_id, key)
    if existing:
        raise ValueError(
            f"ETL source '{key}' already exists for tenant '{tenant_id}' "
            f"(id={existing.id}). Delete it under Settings → Source Databases "
            "or use a different source key."
        )

    try:
        row = etl_src.create_source(
            platform_db,
            tenant_id,
            source_key=source_key,
            display_name=display_name,
            source_type=source_type,
            connection_id=None,
            host=host,
            port=port,
            database_name=database_name,
            username=username,
            password_encrypted=encrypt_password(password),
            source_schema=source_schema,
            extractor_profile=extractor_profile,
            mapping_variant=mapping_variant,
            is_primary=is_primary,
            priority=priority,
        )
    except IntegrityError as exc:
        if "uq_tenant_etl_sources_key" in str(exc).lower():
            raise ValueError(
                f"ETL source '{key}' already exists for tenant '{tenant_id}'. "
                "Delete it under Settings → Source Databases or use a different source key."
            ) from exc
        raise

    sync_tenant_registry_primary(platform_db, tenant_id)

    view = _view_from_row(row) or _row_to_view(platform_db, mart_db, row)
    if not view:
        raise RuntimeError("Source database created but could not be loaded")
    return view


def delete_legacy_source_database(
    platform_db: Session,
    mart_db: Optional[Session],
    tenant_id: str,
    *,
    delete_connection: bool = True,
) -> bool:
    """Remove primary source stored only in tenant_registry (synthetic id=0 in the UI)."""
    reg = tenant_src.get_tenant_source(platform_db, tenant_id)
    if not reg:
        return False
    has_inline = bool(reg.get("mysql_host"))
    connection_id = reg.get("source_connection_id")
    if not has_inline and not connection_id:
        return False

    if delete_connection and connection_id and mart_db is not None:
        conn_svc = DatabaseConnectionService(mart_db)
        conn_svc.delete_connection(int(connection_id))

    platform_db.execute(
        text(
            """
            UPDATE hrm_control.tenant_registry SET
                mysql_host = NULL,
                mysql_port = NULL,
                mysql_db = NULL,
                mysql_user = NULL,
                mysql_password_enc = NULL,
                source_connection_id = NULL
            WHERE tenant_id = :tid
            """
        ),
        {"tid": tenant_id},
    )
    platform_db.commit()
    return True


def delete_source_database(
    platform_db: Session,
    mart_db: Optional[Session],
    tenant_id: str,
    source_id: int,
    *,
    delete_connection: bool = True,
) -> bool:
    if source_id == 0:
        return delete_legacy_source_database(
            platform_db,
            mart_db,
            tenant_id,
            delete_connection=delete_connection,
        )

    rows = etl_src.list_sources(platform_db, tenant_id)
    target = next((r for r in rows if r.id == source_id), None)
    if not target:
        return False

    connection_id = target.connection_id
    deleted = etl_src.delete_source(platform_db, tenant_id, source_id)
    if not deleted:
        return False

    if (
        delete_connection
        and connection_id
        and not target.has_control_plane_credentials()
        and mart_db is not None
    ):
        conn_svc = DatabaseConnectionService(mart_db)
        conn_svc.delete_connection(int(connection_id))

    sync_tenant_registry_primary(platform_db, tenant_id)
    return True


def sync_tenant_registry_primary(
    platform_db: Session,
    tenant_id: str,
) -> None:
    """Keep tenant_registry display name in sync; do not copy source credentials into registry."""
    rows = etl_src.list_sources(platform_db, tenant_id)
    if not rows:
        return
    primary = next((r for r in rows if r.is_primary), rows[0])
    platform_db.execute(
        text(
            """
            UPDATE hrm_control.tenant_registry
            SET display_name = COALESCE(:dn, display_name),
                is_active = TRUE
            WHERE tenant_id = :tid
            """
        ),
        {"tid": tenant_id, "dn": primary.display_name},
    )
    platform_db.commit()


def resolve_config_sync(
    tenant_id: str,
    *,
    source_row: Optional[etl_src.TenantEtlSourceRow] = None,
    connection_id: Optional[int] = None,
) -> TenantSourceConfig:
    """Resolve TenantSourceConfig for ETL — control-plane sources first."""
    if source_row and source_row.has_control_plane_credentials():
        return config_from_etl_source_row(source_row)

    platform_pg = get_platform_engine_sync()
    warehouse_pg = get_warehouse_engine_sync(tenant_id, provision=False)
    layout = get_layout_sync(tenant_id)

    try:
        if connection_id is not None:
            return _load_from_database_connection(
                warehouse_pg,
                int(connection_id),
                tenant_id,
                mart_schema=layout.mart_schema,
            )

        if source_row and source_row.connection_id:
            return _load_from_database_connection(
                warehouse_pg,
                int(source_row.connection_id),
                tenant_id,
                mart_schema=layout.mart_schema,
            )

        from app.services.hr_etl.source_connection import load_tenant_source

        return load_tenant_source(
            platform_pg,
            tenant_id,
            mart_pg=warehouse_pg,
            mart_schema=layout.mart_schema,
        )
    finally:
        warehouse_pg.dispose()


def build_engine_for_etl_source(
    tenant_id: str,
    source: etl_src.TenantEtlSourceRow,
) -> tuple[Any, TenantSourceConfig]:
    """Build SQLAlchemy engine for an ETL source row (used by multi_source_runner)."""
    if source.id == 0:
        config = resolve_config_sync(tenant_id)
    else:
        config = resolve_config_sync(tenant_id, source_row=source)
    return build_source_engine(config), config
