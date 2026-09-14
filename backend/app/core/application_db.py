"""Application PostgreSQL — config, tenants, ETL source registry (hrm_control).

Separate from:
  - Customer warehouse DBs (hrm_wh_{tenant_id}) — analytics / staging / marts
  - Customer source DBs (MySQL / PostgreSQL) — read-only ETL inputs
"""
from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import quote_plus, urlparse, urlunparse

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.core.config import settings

logger = logging.getLogger("application_db")

_PG_SCHEME = re.compile(r"^postgresql(\+[\w]+)?://", re.I)


def _normalize_scheme(url: str, driver: str | None) -> str:
    """Ensure postgresql URL; optional driver suffix (+psycopg2)."""
    if not url:
        return url
    m = _PG_SCHEME.match(url)
    if not m:
        return url
    if driver:
        return _PG_SCHEME.sub(f"postgresql+{driver}://", url, count=1)
    return _PG_SCHEME.sub("postgresql://", url, count=1)


def postgres_sync_url(raw_url: str) -> str:
    """Normalize any Postgres URL to postgresql+psycopg2, preserving query params."""
    if not raw_url:
        return raw_url
    return _normalize_scheme(raw_url, "psycopg2")


def with_database(url: str, database: str, *, driver: str | None = None) -> str:
    """Return the same connection URL pointed at ``database``."""
    normalized = _normalize_scheme(url, driver)
    parsed = urlparse(normalized)
    path = f"/{database.lstrip('/')}"
    return urlunparse(parsed._replace(path=path))


def connection_parts(url: str) -> dict[str, Any]:
    p = urlparse(_normalize_scheme(url, None))
    return {
        "user": p.username or "postgres",
        "password": p.password or "",
        "host": p.hostname or "localhost",
        "port": p.port or 5432,
        "database": (p.path or "/postgres").lstrip("/") or "postgres",
    }


def build_url(
    *,
    host: str,
    port: int,
    user: str,
    password: str,
    database: str,
    driver: str | None = None,
    query: str = "",
) -> str:
    pw = quote_plus(password) if password else ""
    auth = f"{quote_plus(user)}:{pw}@" if pw else f"{quote_plus(user)}@"
    base = f"postgresql://{auth}{host}:{port}/{database}"
    if query:
        sep = "&" if "?" in base else "?"
        base = f"{base}{sep}{query.lstrip('?')}"
    return _normalize_scheme(base, driver)


def create_postgres_engine(url: str, *, pool_pre_ping: bool = True) -> Engine:
    """Create a sync SQLAlchemy engine using psycopg2."""
    return create_engine(postgres_sync_url(url), pool_pre_ping=pool_pre_ping)


def application_sync_url() -> str:
    """Sync URL for the application database (API, Alembic, scripts)."""
    return postgres_sync_url(settings.application_database_url)


def admin_sync_url() -> str:
    """Connect to app-server maintenance DB (``postgres``) — only when APP_AUTO_PROVISION=true."""
    if settings.POSTGRES_ADMIN_URL:
        return postgres_sync_url(settings.POSTGRES_ADMIN_URL)
    base = settings.application_database_url
    return with_database(base, "postgres", driver="psycopg2")


def get_application_engine_sync() -> Engine:
    return create_postgres_engine(settings.application_database_url)


def get_postgres_admin_engine_sync() -> Engine:
    return create_postgres_engine(admin_sync_url())


def ensure_application_database() -> None:
    """Create APP_DATABASE_NAME on the server if missing (when APP_AUTO_PROVISION)."""
    if not settings.APP_AUTO_PROVISION:
        return

    app_db = settings.APP_DATABASE_NAME.strip()
    if not app_db:
        return

    admin = get_postgres_admin_engine_sync()
    try:
        with admin.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            row = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :db"),
                {"db": app_db},
            ).first()
            if row:
                logger.debug("Application database %s already exists", app_db)
                return
            conn.execute(text(f'CREATE DATABASE "{app_db}"'))
            logger.info("Created application database %s", app_db)
    finally:
        admin.dispose()

    app_eng = get_application_engine_sync()
    try:
        with app_eng.begin() as conn:
            conn.execute(text("CREATE SCHEMA IF NOT EXISTS hrm_control"))
    finally:
        app_eng.dispose()


# Backward-compatible alias
def platform_sync_url() -> str:
    return application_sync_url()
