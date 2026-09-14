"""MintHRM — TenantRegistry SQLAlchemy model.

Maps to hrm_control.tenant_registry — one row per customer (identity + warehouse).

Customer source DB credentials belong in tenant_etl_sources, not here.
Legacy mysql_* columns remain for backward compatibility but should be NULL.

This is the only table managed by alembic migrations; all per-tenant mart
tables are created dynamically by TenantManager.ensure_schemas_exist().
"""
from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func

from app.core.database import Base


class TenantRegistry(Base):
    """One row per registered customer tenant."""

    __tablename__ = "tenant_registry"
    __table_args__ = {"schema": "hrm_control"}

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(128), nullable=False, unique=True, index=True)
    display_name = Column(String(255), nullable=False)

    # Legacy source fields — deprecated; use tenant_etl_sources instead.
    source_type = Column(String(32), nullable=False, default="mysql")
    mysql_host = Column(String(255), nullable=True)
    mysql_port = Column(Integer, nullable=True)
    mysql_db = Column(String(255), nullable=True)
    mysql_user = Column(String(255), nullable=True)
    mysql_password_enc = Column(Text, nullable=True)
    source_connection_id = Column(Integer, nullable=True)

    warehouse_host = Column(String(255), nullable=True)
    warehouse_port = Column(Integer, nullable=True)
    warehouse_db = Column(String(128), nullable=True)
    warehouse_user = Column(String(255), nullable=True)
    warehouse_password_enc = Column(Text, nullable=True)

    is_active = Column(Boolean, nullable=False, default=True)
    last_etl_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
