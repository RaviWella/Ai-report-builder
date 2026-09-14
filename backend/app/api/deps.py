"""Shared FastAPI dependencies for the v1 routers."""

from __future__ import annotations

from collections.abc import Generator

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.tenancy import TenantContext, get_tenant_context
from app.db.pg_tenant_session import get_postgres_tenant_session_manager
from app.db.postgres import get_platform_db

DbSession = Session


def get_tenant_pg_db(
    ctx: TenantContext = Depends(get_tenant_context),
) -> Generator[Session, None, None]:
    """Tenant-scoped metadata DB session (search_path set, schema provisioned)."""
    with get_postgres_tenant_session_manager().scope(ctx.tenant_id) as session:
        yield session


# Routers import this name — now tenant-scoped via search_path.
db_session = get_tenant_pg_db


def platform_db_session() -> Generator[Session, None, None]:
    """Platform schema session for cross-tenant admin routes."""
    yield from get_platform_db()
