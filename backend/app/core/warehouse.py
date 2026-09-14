"""Per-tenant warehouse: one Postgres database per customer (schemas hr_raw, hr, …).

Application DB (APPLICATION_DATABASE_URL / hrm_platform): hrm_control, tenant_registry.
Warehouse DBs (hrm_wh_*): per-tenant analytics only.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Literal, Optional
from urllib.parse import quote_plus, urlparse

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from app.core.application_db import create_postgres_engine, postgres_sync_url
from app.core.config import settings

logger = logging.getLogger("warehouse")

IsolationMode = Literal["database", "schema"]

_REGISTRY_SQL = """
    SELECT tenant_id, warehouse_host, warehouse_port, warehouse_db,
           warehouse_user, warehouse_password_enc
    FROM hrm_control.tenant_registry
    WHERE tenant_id = :tid
"""

_layout_cache: dict[str, "WarehouseLayout"] = {}
_sync_engines: dict[str, Engine] = {}


@dataclass(frozen=True)
class WarehouseLayout:
    tenant_id: str
    isolation: IsolationMode
    raw_schema: str
    mart_schema: str
    semantic_schema: str
    custom_reports_schema: str
    control_schema: str
    snap_schema: str
    database_name: Optional[str] = None

    @property
    def uses_dedicated_database(self) -> bool:
        return self.isolation == "database"


def default_warehouse_db_name(tenant_id: str) -> str:
    prefix = (settings.WAREHOUSE_DB_PREFIX or "hrm_wh_").strip()
    return f"{prefix}{tenant_id}"


def layout_for_tenant(tenant_id: str, *, warehouse_db: Optional[str] = None) -> WarehouseLayout:
    db_name = (warehouse_db or "").strip() or None
    if db_name:
        return WarehouseLayout(
            tenant_id=tenant_id,
            isolation="database",
            raw_schema="hr_raw",
            mart_schema="hr",
            semantic_schema="hr_semantic",
            custom_reports_schema="custom_reports",
            control_schema="hr_control",
            snap_schema="hr_snap",
            database_name=db_name,
        )
    return WarehouseLayout(
        tenant_id=tenant_id,
        isolation="schema",
        raw_schema=f"{tenant_id}_hr_raw",
        mart_schema=f"{tenant_id}_hr",
        semantic_schema=f"{tenant_id}_hr_semantic",
        custom_reports_schema=f"{tenant_id}_custom_reports",
        control_schema=f"{tenant_id}_hr_control",
        snap_schema=f"{tenant_id}_hr_snap",
        database_name=None,
    )


def platform_sync_url() -> str:
    from app.core.application_db import application_sync_url

    return application_sync_url()


def _platform_defaults() -> dict[str, Any]:
    from app.core.application_db import connection_parts

    p = connection_parts(settings.application_database_url)
    return {
        "user": p["user"],
        "password": p["password"],
        "host": p["host"],
        "port": p["port"],
        "database": p["database"],
    }


def _app_admin_defaults() -> dict[str, Any]:
    """Postgres admin on the application server (local dev fallback)."""
    from app.core.application_db import admin_sync_url, connection_parts

    p = connection_parts(admin_sync_url())
    return {
        "user": p["user"],
        "password": p["password"],
        "host": p["host"],
        "port": p["port"],
        "database": p["database"],
    }


def _warehouse_env_defaults() -> Optional[dict[str, Any]]:
    """Global warehouse server from env (production: separate analytics cluster)."""
    host = (settings.WAREHOUSE_DEFAULT_HOST or "").strip()
    if not host:
        return None
    user = (settings.WAREHOUSE_DEFAULT_USER or "").strip()
    if not user:
        return None
    return {
        "host": host,
        "port": int(settings.WAREHOUSE_DEFAULT_PORT or 5432),
        "user": user,
        "password": settings.WAREHOUSE_DEFAULT_PASSWORD or "",
        "database": "postgres",
    }


def _warehouse_connection_defaults() -> dict[str, Any]:
    """Resolve warehouse host/user/password when tenant_registry columns are NULL."""
    env_wh = _warehouse_env_defaults()
    if env_wh:
        return env_wh
    return _app_admin_defaults()


def warehouse_admin_sync_url() -> str:
    """Maintenance connection on the warehouse Postgres server (CREATE DATABASE)."""
    from app.core.application_db import build_url, with_database

    if settings.WAREHOUSE_ADMIN_URL:
        from app.core.application_db import _normalize_scheme

        admin_db = (settings.WAREHOUSE_ADMIN_DATABASE or "postgres").strip() or "postgres"
        return with_database(
            _normalize_scheme(settings.WAREHOUSE_ADMIN_URL, "psycopg2"),
            admin_db,
            driver="psycopg2",
        )
    env_wh = _warehouse_env_defaults()
    if env_wh:
        return build_url(
            host=env_wh["host"],
            port=env_wh["port"],
            user=env_wh["user"],
            password=env_wh["password"],
            database="postgres",
            driver="psycopg2",
        )
    # Local dev: app and warehouse share one Postgres instance
    from app.core.application_db import admin_sync_url

    return admin_sync_url()


def get_warehouse_admin_engine_sync() -> Engine:
    return create_postgres_engine(warehouse_admin_sync_url())


def _decrypt_password(enc: Optional[str]) -> Optional[str]:
    if not enc:
        return None
    if not settings.DB_ENCRYPTION_KEY:
        return enc
    from cryptography.fernet import Fernet

    return Fernet(settings.DB_ENCRYPTION_KEY.encode()).decrypt(enc.encode()).decode()


def _sync_url(host: str, port: int, user: str, password: str, database: str) -> str:
    pw = quote_plus(password) if password else ""
    auth = f"{quote_plus(user)}:{pw}@" if pw else f"{quote_plus(user)}@"
    return postgres_sync_url(f"postgresql://{auth}{host}:{port}/{database}")


def _fetch_registry(tenant_id: str) -> Optional[dict[str, Any]]:
    eng = get_platform_engine_sync()
    with eng.connect() as conn:
        row = conn.execute(text(_REGISTRY_SQL), {"tid": tenant_id}).mappings().first()
        return dict(row) if row else None


def invalidate_tenant_cache(tenant_id: str) -> None:
    _layout_cache.pop(tenant_id, None)
    old = _sync_engines.pop(tenant_id, None)
    if old:
        old.dispose()
def get_layout_sync(tenant_id: str) -> WarehouseLayout:
    if tenant_id in _layout_cache:
        return _layout_cache[tenant_id]
    row = _fetch_registry(tenant_id)
    wh_db = row.get("warehouse_db") if row else None
    if not wh_db and settings.WAREHOUSE_DEFAULT_ISOLATION == "database":
        wh_db = default_warehouse_db_name(tenant_id)
    layout = layout_for_tenant(tenant_id, warehouse_db=wh_db)
    _layout_cache[tenant_id] = layout
    return layout


def connection_params(tenant_id: str) -> dict[str, Any]:
    layout = get_layout_sync(tenant_id)
    defaults = _warehouse_connection_defaults()
    row = _fetch_registry(tenant_id) or {}
    if layout.uses_dedicated_database:
        return {
            "host": row.get("warehouse_host") or defaults["host"],
            "port": int(row.get("warehouse_port") or defaults["port"]),
            "user": row.get("warehouse_user") or defaults["user"],
            "password": _decrypt_password(row.get("warehouse_password_enc"))
            or defaults["password"],
            "database": layout.database_name or default_warehouse_db_name(tenant_id),
        }
    # Legacy schema mode: warehouse tables live on the application database
    app = _platform_defaults()
    return {
        "host": app["host"],
        "port": app["port"],
        "user": app["user"],
        "password": app["password"],
        "database": app["database"],
    }


def get_platform_engine_sync() -> Engine:
    from app.core.application_db import get_application_engine_sync

    return get_application_engine_sync()


def provision_warehouse_database(tenant_id: str, params: dict[str, Any]) -> None:
    db_name = params["database"]
    layout = get_layout_sync(tenant_id)

    admin = get_warehouse_admin_engine_sync()
    with admin.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        if not conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :db"), {"db": db_name}
        ).first():
            conn.execute(text(f'CREATE DATABASE "{db_name}"'))
            logger.info("Created warehouse database %s", db_name)

    wh = create_postgres_engine(
        _sync_url(
            params["host"],
            params["port"],
            params["user"],
            params["password"],
            db_name,
        )
    )
    try:
        with wh.begin() as conn:
            for schema in (
                layout.raw_schema,
                layout.mart_schema,
                layout.semantic_schema,
                layout.custom_reports_schema,
                layout.control_schema,
                layout.snap_schema,
            ):
                conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
            for ddl in control_schema_ddl(layout.control_schema):
                conn.execute(text(ddl))
            from app.services.hr_etl.data_dictionary_schema import ensure_data_dictionary_tables

            ensure_data_dictionary_tables(conn, tenant_id)
            from app.core.mart_metadata import ensure_mart_metadata_tables

            ensure_mart_metadata_tables(conn, layout.mart_schema)
    finally:
        wh.dispose()


def get_warehouse_engine_sync(tenant_id: str, *, provision: bool = True) -> Engine:
    if tenant_id in _sync_engines:
        return _sync_engines[tenant_id]
    layout = get_layout_sync(tenant_id)
    params = connection_params(tenant_id)
    if layout.uses_dedicated_database and provision and settings.WAREHOUSE_AUTO_PROVISION:
        try:
            provision_warehouse_database(tenant_id, params)
        except OperationalError as exc:
            logger.warning(
                "Warehouse auto-provision failed for %s (%s); will connect if DB already exists",
                tenant_id,
                exc,
            )
    url = _sync_url(
        params["host"],
        params["port"],
        params["user"],
        params["password"],
        params["database"],
    )
    engine = create_postgres_engine(url)
    _sync_engines[tenant_id] = engine
    return engine


def dbt_vars(tenant_id: str) -> dict[str, str]:
    layout = get_layout_sync(tenant_id)
    return {
        "tenant_id": tenant_id,
        "raw_schema": layout.raw_schema,
        "mart_schema": layout.mart_schema,
        "semantic_schema": layout.semantic_schema,
        "custom_reports_schema": layout.custom_reports_schema,
        "control_schema": layout.control_schema,
        "snap_schema": layout.snap_schema,
    }


MART_TABLES = ("database_connections", "data_access_rules")


def control_schema_ddl(control_schema: str) -> list[str]:
    """Idempotent DDL for ETL governance tables in the tenant warehouse."""
    return [
        f"""
        CREATE TABLE IF NOT EXISTS "{control_schema}".hr_etl_run_log (
            run_id SERIAL PRIMARY KEY,
            run_type VARCHAR(32) NOT NULL,
            triggered_by VARCHAR(128),
            status VARCHAR(32) DEFAULT 'running',
            started_at TIMESTAMPTZ DEFAULT NOW(),
            completed_at TIMESTAMPTZ,
            rows_extracted INTEGER DEFAULT 0,
            rows_loaded INTEGER DEFAULT 0,
            rows_transformed INTEGER DEFAULT 0,
            error_message TEXT,
            details JSONB
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS "{control_schema}".hr_etl_step_log (
            step_id SERIAL PRIMARY KEY,
            run_id INTEGER REFERENCES "{control_schema}".hr_etl_run_log(run_id),
            step_name VARCHAR(128) NOT NULL,
            step_type VARCHAR(32),
            status VARCHAR(32) DEFAULT 'running',
            started_at TIMESTAMPTZ DEFAULT NOW(),
            completed_at TIMESTAMPTZ,
            rows_processed INTEGER DEFAULT 0,
            error_message TEXT,
            details JSONB
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS "{control_schema}".hr_etl_watermark (
            table_name VARCHAR(128) PRIMARY KEY,
            last_value TIMESTAMPTZ,
            rows_at_mark INTEGER DEFAULT 0,
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS "{control_schema}".hr_validation_result (
            id SERIAL PRIMARY KEY,
            run_id INTEGER,
            check_name VARCHAR(128),
            severity VARCHAR(16),
            status VARCHAR(16),
            message TEXT,
            checked_at TIMESTAMPTZ DEFAULT NOW()
        )
        """,
    ]


def ensure_warehouse_ready_sync(pg: Engine, tenant_id: str, *, force: bool = False) -> None:
    """Create warehouse schemas, control DDL, mart clones, and staging tables (sync ETL path)."""
    from app.core.tenant import is_warehouse_layers_ready, mark_warehouse_layers_ready
    from app.services.hr_etl.staging_schema import ensure_staging_tables

    layout = get_layout_sync(tenant_id)
    if not force and is_warehouse_layers_ready(tenant_id):
        ensure_staging_tables(pg, tenant_id)
        return
    with pg.begin() as conn:
        for schema in (
            layout.raw_schema,
            layout.mart_schema,
            layout.semantic_schema,
            layout.custom_reports_schema,
            layout.control_schema,
            layout.snap_schema,
        ):
            conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))

        for ddl in control_schema_ddl(layout.control_schema):
            conn.execute(text(ddl))

        from app.services.hr_etl.data_dictionary_schema import ensure_data_dictionary_tables

        ensure_data_dictionary_tables(conn, tenant_id)

        from app.core.mart_metadata import ensure_mart_metadata_tables

        ensure_mart_metadata_tables(conn, layout.mart_schema)

    ensure_staging_tables(pg, tenant_id)
    from app.services.hr_etl.custom_reports_catalog import ensure_default_reports_sync
    from app.services.hr_etl.custom_reports_sync import sync_tenant_custom_report_views

    try:
        ensure_default_reports_sync(tenant_id)
        sync_tenant_custom_report_views(tenant_id, pg=pg, ensure_defaults=False)
    except Exception as exc:
        logger.warning(
            "Custom report sync skipped for tenant=%s (%s)",
            tenant_id,
            exc,
        )
    mark_warehouse_layers_ready(tenant_id)
    logger.info(
        "Warehouse ready for tenant=%s db=%s isolation=%s",
        tenant_id,
        layout.database_name or "platform",
        layout.isolation,
    )

