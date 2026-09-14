"""Multiple ETL sources per tenant — MySQL legacy + PostgreSQL product schemas."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.hr_etl.source_connection import (
    SourceType,
    TenantSourceConfig,
    load_tenant_source,
    normalize_source_type,
)

logger = logging.getLogger("tenant_etl_sources")

_SELECT = """
    SELECT id, tenant_id, source_key, display_name, source_type,
           connection_id, source_schema, extractor_profile, mapping_variant,
           is_primary, is_active, priority,
           host, port, database_name, username, password_encrypted
    FROM hrm_control.tenant_etl_sources
    WHERE tenant_id = :tid AND is_active = TRUE
    ORDER BY is_primary DESC, priority ASC, id ASC
"""


@dataclass(frozen=True)
class TenantEtlSourceRow:
    id: int
    tenant_id: str
    source_key: str
    display_name: str
    source_type: SourceType
    connection_id: Optional[int]
    source_schema: Optional[str]
    extractor_profile: str
    mapping_variant: Optional[str]
    is_primary: bool
    is_active: bool
    priority: int
    host: Optional[str] = None
    port: Optional[int] = None
    database_name: Optional[str] = None
    username: Optional[str] = None
    password_encrypted: Optional[str] = None

    def has_control_plane_credentials(self) -> bool:
        """Credentials stored on tenant_etl_sources (management DB)."""
        return bool(
            (self.host or "").strip()
            and (self.database_name or "").strip()
            and (self.username or "").strip()
            and (self.password_encrypted or "").strip()
        )

    @property
    def staging_suffix(self) -> str:
        """Empty for primary (writes stg_*); else suffix stg_*__{key}."""
        return "" if self.is_primary else self.source_key

    def mapping_variant_resolved(self) -> SourceType:
        if self.mapping_variant:
            return normalize_source_type(self.mapping_variant)
        return self.source_type


def _row_to_dataclass(row: Dict[str, Any]) -> TenantEtlSourceRow:
    return TenantEtlSourceRow(
        id=int(row["id"]),
        tenant_id=row["tenant_id"],
        source_key=row["source_key"],
        display_name=row["display_name"],
        source_type=normalize_source_type(row["source_type"]),
        connection_id=row.get("connection_id"),
        source_schema=row.get("source_schema"),
        extractor_profile=(row.get("extractor_profile") or "minthrm").strip(),
        mapping_variant=row.get("mapping_variant"),
        is_primary=bool(row.get("is_primary")),
        is_active=bool(row.get("is_active", True)),
        priority=int(row.get("priority") or 0),
        host=row.get("host"),
        port=int(row["port"]) if row.get("port") is not None else None,
        database_name=row.get("database_name"),
        username=row.get("username"),
        password_encrypted=row.get("password_encrypted"),
    )


def _is_missing_etl_sources_table(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return "tenant_etl_sources" in msg and (
        "does not exist" in msg or "undefinedtable" in msg or "undefined table" in msg
    )


def resolve_legacy_single_source_async(
    db: Session, tenant_id: str
) -> List[TenantEtlSourceRow]:
    """When tenant_etl_sources is empty or missing, synthesize one row from tenant_registry."""
    from app.services import tenant_source as tenant_src

    row = tenant_src.get_tenant_source(db, tenant_id)
    if not row:
        return []
    if not row.get("mysql_host") and not row.get("source_connection_id"):
        return []

    st = normalize_source_type(row["source_type"])
    return [
        TenantEtlSourceRow(
            id=0,
            tenant_id=tenant_id,
            source_key="legacy",
            display_name=row.get("display_name") or "Legacy source (tenant_registry)",
            source_type=st,
            connection_id=row.get("source_connection_id"),
            source_schema=None,
            extractor_profile=settings.MYSQL_EXTRACTOR_PROFILE or "minthrm",
            mapping_variant=None,
            is_primary=True,
            is_active=True,
            priority=0,
        )
    ]


def list_sources(db: Session, tenant_id: str) -> List[TenantEtlSourceRow]:
    result = db.execute(text(_SELECT), {"tid": tenant_id})
    return [_row_to_dataclass(dict(r)) for r in result.mappings().all()]


def list_sources_for_api(
    db: Session, tenant_id: str
) -> List[TenantEtlSourceRow]:
    """List ETL sources for the settings UI; falls back to tenant_registry when needed."""
    try:
        rows = list_sources(db, tenant_id)
    except ProgrammingError as exc:
        if not _is_missing_etl_sources_table(exc):
            raise
        db.rollback()
        logger.warning(
            "tenant_etl_sources table missing for tenant=%s — using tenant_registry fallback. "
            "Run: cd backend && alembic upgrade head",
            tenant_id,
        )
        rows = []
    if rows:
        return rows
    return resolve_legacy_single_source_async(db, tenant_id)


def list_sources_sync(pg: Engine, tenant_id: str) -> List[TenantEtlSourceRow]:
    try:
        with pg.connect() as conn:
            result = conn.execute(text(_SELECT), {"tid": tenant_id})
            return [_row_to_dataclass(dict(r)) for r in result.mappings().all()]
    except ProgrammingError as exc:
        if not _is_missing_etl_sources_table(exc):
            raise
        logger.warning(
            "tenant_etl_sources table missing for tenant=%s — using tenant_registry fallback. "
            "Run: cd backend && alembic upgrade head",
            tenant_id,
        )
        return []


def resolve_legacy_single_source(platform_pg: Engine, tenant_id: str) -> List[TenantEtlSourceRow]:
    """When tenant_etl_sources is empty, synthesize one row from tenant_registry."""
    with platform_pg.connect() as conn:
        reg = conn.execute(
            text(
                """
                SELECT display_name, source_type, mysql_host, source_connection_id
                FROM hrm_control.tenant_registry
                WHERE tenant_id = :tid
                """
            ),
            {"tid": tenant_id},
        ).mappings().first()
    if not reg or (not reg.get("mysql_host") and not reg.get("source_connection_id")):
        return []

    st = normalize_source_type(reg.get("source_type"))
    return [
        TenantEtlSourceRow(
            id=0,
            tenant_id=tenant_id,
            source_key="legacy",
            display_name=reg.get("display_name") or "Legacy source (tenant_registry)",
            source_type=st,
            connection_id=reg.get("source_connection_id"),
            source_schema=None,
            extractor_profile=settings.MYSQL_EXTRACTOR_PROFILE or "minthrm",
            mapping_variant=None,
            is_primary=True,
            is_active=True,
            priority=0,
        )
    ]


def load_sources_for_etl(platform_pg: Engine, tenant_id: str) -> List[TenantEtlSourceRow]:
    """Active sources for an ETL run (queries platform hrm_control)."""
    rows = list_sources_sync(platform_pg, tenant_id)
    if rows:
        return rows
    return resolve_legacy_single_source(platform_pg, tenant_id)


def build_engine_for_source(
    warehouse_pg: Engine,
    tenant_id: str,
    source: TenantEtlSourceRow,
) -> tuple[Engine, TenantSourceConfig]:
    """Build source DB engine via unified source_databases resolver."""
    from app.services.source_databases import build_engine_for_etl_source

    return build_engine_for_etl_source(tenant_id, source)


def normalize_source_key(source_key: str) -> str:
    key = source_key.strip().lower().replace(" ", "_")
    if not key or not key.replace("_", "").isalnum():
        raise ValueError("source_key must be alphanumeric (underscores allowed)")
    return key


def find_source_by_key(
    db: Session, tenant_id: str, source_key: str
) -> Optional[TenantEtlSourceRow]:
    key = normalize_source_key(source_key)
    result = db.execute(
        text(
            """
            SELECT id, tenant_id, source_key, display_name, source_type,
                   connection_id, source_schema, extractor_profile, mapping_variant,
                   is_primary, is_active, priority,
                   host, port, database_name, username, password_encrypted
            FROM hrm_control.tenant_etl_sources
            WHERE tenant_id = :tid AND source_key = :key
            LIMIT 1
            """
        ),
        {"tid": tenant_id, "key": key},
    )
    row = result.mappings().first()
    return _row_to_dataclass(dict(row)) if row else None


def create_source(
    db: Session,
    tenant_id: str,
    *,
    source_key: str,
    display_name: str,
    source_type: str,
    connection_id: Optional[int] = None,
    host: Optional[str] = None,
    port: Optional[int] = None,
    database_name: Optional[str] = None,
    username: Optional[str] = None,
    password_encrypted: Optional[str] = None,
    source_schema: Optional[str] = None,
    extractor_profile: str = "minthrm",
    mapping_variant: Optional[str] = None,
    is_primary: bool = False,
    priority: int = 0,
) -> TenantEtlSourceRow:
    st = normalize_source_type(source_type)
    key = normalize_source_key(source_key)
    existing = find_source_by_key(db, tenant_id, key)
    if existing:
        raise ValueError(
            f"ETL source '{key}' already exists for tenant '{tenant_id}' "
            f"(id={existing.id}). Delete it under Settings → Source Databases "
            "or use a different source key."
        )

    if is_primary:
        db.execute(
            text(
                "UPDATE hrm_control.tenant_etl_sources SET is_primary = FALSE"
                " WHERE tenant_id = :tid"
            ),
            {"tid": tenant_id},
        )

    result = db.execute(
        text(
            """
            INSERT INTO hrm_control.tenant_etl_sources
                (tenant_id, source_key, display_name, source_type, connection_id,
                 host, port, database_name, username, password_encrypted,
                 source_schema, extractor_profile, mapping_variant,
                 is_primary, is_active, priority)
            VALUES
                (:tid, :key, :dn, :stype, :cid,
                 :host, :port, :dbname, :user, :pwd,
                 :schema, :profile, :variant,
                 :primary, TRUE, :prio)
            RETURNING id, tenant_id, source_key, display_name, source_type,
                      connection_id, source_schema, extractor_profile, mapping_variant,
                      is_primary, is_active, priority,
                      host, port, database_name, username, password_encrypted
            """
        ),
        {
            "tid": tenant_id,
            "key": key,
            "dn": display_name,
            "stype": st,
            "cid": connection_id,
            "host": (host or "").strip() or None,
            "port": port,
            "dbname": (database_name or "").strip() or None,
            "user": (username or "").strip() or None,
            "pwd": password_encrypted,
            "schema": source_schema or None,
            "profile": extractor_profile,
            "variant": mapping_variant,
            "primary": is_primary,
            "prio": priority,
        },
    )
    db.commit()
    row = result.mappings().first()
    if not row:
        raise RuntimeError("Failed to create tenant_etl_source")
    return _row_to_dataclass(dict(row))


def delete_source(db: Session, tenant_id: str, source_id: int) -> bool:
    result = db.execute(
        text(
            "DELETE FROM hrm_control.tenant_etl_sources"
            " WHERE tenant_id = :tid AND id = :sid RETURNING id"
        ),
        {"tid": tenant_id, "sid": source_id},
    )
    db.commit()
    return result.scalar() is not None
