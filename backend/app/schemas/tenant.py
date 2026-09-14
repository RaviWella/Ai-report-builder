"""MintHRM — tenant management Pydantic schemas.

Extracted from tenant_routes.py to follow the mint-analytics pattern of
keeping all Pydantic models in app/schemas/.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel


class TenantCreate(BaseModel):
    tenant_id: str
    display_name: str
    source_type: Literal["mysql", "postgres"] = "mysql"
    mysql_host: str
    mysql_port: Optional[int] = None
    mysql_db: str
    mysql_user: str
    mysql_password: str


class TenantProvisionMinimal(BaseModel):
    """Register tenant for HRIS launch / analytics — no customer source DB yet."""

    tenant_id: str
    display_name: Optional[str] = None
    warehouse_db: Optional[str] = None


class TenantProvisionResponse(BaseModel):
    tenant_id: str
    display_name: str
    warehouse_db: str
    created: bool
    message: str


class TenantResponse(BaseModel):
    tenant_id: str
    display_name: str
    source_type: str = "mysql"
    mysql_host: Optional[str] = None
    mysql_port: Optional[int] = None
    mysql_db: Optional[str] = None
    is_active: bool
    last_etl_at: Optional[str] = None


class TenantSourceResponse(BaseModel):
    """ETL source DB for the current tenant (password never returned)."""

    tenant_id: str
    configured: bool
    display_name: Optional[str] = None
    source_type: str = "mysql"
    mysql_host: Optional[str] = None
    mysql_port: Optional[int] = None
    mysql_db: Optional[str] = None
    mysql_user: Optional[str] = None
    has_password: bool = False
    is_active: bool = True
    last_etl_at: Optional[str] = None
    extractor_profile: str = "generic"
    # Dynamic connection — when set, ETL uses this saved DatabaseConnection
    source_connection_id: Optional[int] = None
    source_connection_name: Optional[str] = None
    source_connection_engine: Optional[str] = None


class TenantSourceConnectionSet(BaseModel):
    """Payload to point a tenant's ETL source at a saved DatabaseConnection."""
    connection_id: Optional[int] = None  # None = clear (revert to legacy fields)


class TenantSourceUpdate(BaseModel):
    display_name: str
    source_type: Literal["mysql", "postgres"] = "mysql"
    mysql_host: str
    mysql_port: Optional[int] = None
    mysql_db: str
    mysql_user: str
    mysql_password: Optional[str] = None


class TenantSourceTest(BaseModel):
    source_type: Literal["mysql", "postgres"] = "mysql"
    mysql_host: str
    mysql_port: Optional[int] = None
    mysql_db: str
    mysql_user: str
    mysql_password: str


class TenantEtlSourceCreate(BaseModel):
    """Register one ETL source for a tenant (PostgreSQL and/or MySQL via connection_id)."""

    source_key: str
    display_name: str
    source_type: Literal["mysql", "postgres"] = "mysql"
    connection_id: Optional[int] = None
    source_schema: Optional[str] = None
    extractor_profile: str = "minthrm"
    mapping_variant: Optional[str] = None
    is_primary: bool = False
    priority: int = 0


class TenantEtlSourceOut(BaseModel):
    id: int
    tenant_id: str
    source_key: str
    display_name: str
    source_type: str
    connection_id: Optional[int] = None
    source_schema: Optional[str] = None
    extractor_profile: str
    mapping_variant: Optional[str] = None
    is_primary: bool
    is_active: bool
    priority: int
    staging_suffix: str = ""


class SourceDatabaseTest(BaseModel):
    """Test source DB connectivity before save (MySQL or PostgreSQL)."""

    source_type: Literal["mysql", "postgres"] = "mysql"
    host: str
    port: Optional[int] = None
    database_name: str
    username: str
    password: str
    source_schema: Optional[str] = None


class SourceDatabaseCreate(BaseModel):
    """Register one ETL source database in a single request (connection + registry)."""

    source_key: str
    display_name: str
    source_type: Literal["mysql", "postgres"] = "mysql"
    host: str
    port: Optional[int] = None
    database_name: str
    username: str
    password: str
    source_schema: Optional[str] = None
    extractor_profile: str = "minthrm"
    mapping_variant: Optional[str] = None
    is_primary: bool = False
    priority: int = 0


class SourceDatabaseOut(BaseModel):
    """ETL source with connection details (password never returned)."""

    id: int
    tenant_id: str
    source_key: str
    display_name: str
    source_type: str
    connection_id: int
    source_schema: Optional[str] = None
    extractor_profile: str
    mapping_variant: Optional[str] = None
    is_primary: bool
    is_active: bool
    priority: int
    staging_suffix: str = ""
    host: str
    port: int
    database_name: str
    username: str
    connection_name: str
    is_healthy: bool = True
