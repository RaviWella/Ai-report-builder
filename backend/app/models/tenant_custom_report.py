"""Maps to hrm_control.tenant_custom_reports — per-tenant report catalog."""
from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func

from app.core.database import Base


class TenantCustomReport(Base):
    __tablename__ = "tenant_custom_reports"
    __table_args__ = {"schema": "hrm_control"}

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(128), nullable=False, index=True)
    module = Column(String(64), nullable=False)
    report_name = Column(String(255), nullable=False)
    view_name = Column(String(128), nullable=False)
    view_query = Column(Text, nullable=True)
    report_type = Column(String(32), nullable=False, default="table")
    source = Column(String(16), nullable=False, default="sync")
    sort_order = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)
    is_system = Column(Boolean, nullable=False, default=False)
    period_year_column = Column(String(64), nullable=True)
    period_month_column = Column(String(64), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
