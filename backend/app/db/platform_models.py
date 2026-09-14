"""Platform schema ORM models (cross-tenant control plane)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class PlatformBase(DeclarativeBase):
    pass


class TenantProvisionStatus(PlatformBase):
    """Tracks which tenants are onboarded for Report Builder PG access."""

    __tablename__ = "tenant_provision_status"
    __table_args__ = {"schema": "platform"}

    subdomain: Mapped[str] = mapped_column(String(255), primary_key=True)
    pg_schema: Mapped[str] = mapped_column(String(63), nullable=False)
    datamart_key: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="active")
    provisioned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    provisioned_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Full boolean map of gated sections, e.g. {"Chat": false, "Documents": true, ...}
    nav_sections: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)


class SystemAIProviderConfig(PlatformBase):
    """Platform-default AI provider config (replaces __system__ tenant row)."""

    __tablename__ = "ai_provider_configs_system"
    __table_args__ = {"schema": "platform"}

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default="system")
    provider: Mapped[str] = mapped_column(String(32), default="anthropic")
    model: Mapped[str] = mapped_column(String(128), default="claude-opus-4-8")
    base_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_by: Mapped[str] = mapped_column(String(64), default="system")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
