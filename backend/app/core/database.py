"""Platform DB (control plane) and per-tenant warehouse DB sessions."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Generator, Optional

from fastapi import Header
from sqlalchemy import text
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.core.application_db import ensure_application_database, get_application_engine_sync
from app.core.config import settings
from app.core.warehouse import (
    ensure_warehouse_ready_sync,
    get_layout_sync,
    get_warehouse_engine_sync,
)

engine = get_application_engine_sync()
SessionLocal = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """Public schema session (hrm_control, datamart chat/workspace, public templates)."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def get_warehouse_db(
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-Id"),
) -> Generator[Session, None, None]:
    """Warehouse session for tenant mart / control / semantic data."""
    if not x_tenant_id:
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()
        return

    layout = get_layout_sync(x_tenant_id)
    wh_engine = get_warehouse_engine_sync(x_tenant_id)
    try:
        ensure_warehouse_ready_sync(wh_engine, x_tenant_id)
    except Exception as exc:
        import logging

        logging.getLogger("tenant").warning(
            "Warehouse setup failed for %s: %s", x_tenant_id, exc
        )

    connection = wh_engine.connect()
    connection.execute(text(f'SET search_path TO "{layout.mart_schema}", public'))
    session = Session(bind=connection, expire_on_commit=False)
    try:
        yield session
    finally:
        session.close()
        connection.close()


def get_tenant_db(
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-Id"),
) -> Generator[Session, None, None]:
    yield from get_warehouse_db(x_tenant_id)


@contextmanager
def get_tenant_session_by_id(tenant_id: str):
    layout = get_layout_sync(tenant_id)
    wh_engine = get_warehouse_engine_sync(tenant_id)
    ensure_warehouse_ready_sync(wh_engine, tenant_id)
    connection = wh_engine.connect()
    connection.execute(text(f'SET search_path TO "{layout.mart_schema}", public'))
    session = Session(bind=connection, expire_on_commit=False)
    try:
        yield session
    finally:
        session.close()
        connection.close()


def init_db_sync() -> None:
    """Ensure application DB exists and hrm_control schema is present.

    Table DDL is owned by Alembic (see run_platform_migrations).
    """
    ensure_application_database()
    with engine.begin() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS hrm_control"))
