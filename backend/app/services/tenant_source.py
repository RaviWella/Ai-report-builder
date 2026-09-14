"""ETL source connection — read/update/test tenant_registry entries."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.hr_etl.source_connection import (
    TenantSourceConfig,
    build_source_engine,
    normalize_source_type,
)

logger = logging.getLogger("tenant_source")

_SELECT = """
    SELECT tenant_id, display_name,
           COALESCE(source_type, 'mysql') AS source_type,
           mysql_host, mysql_port, mysql_db, mysql_user,
           mysql_password_enc, is_active, last_etl_at,
           source_connection_id
    FROM hrm_control.tenant_registry
    WHERE tenant_id = :tid
"""


def _encrypt_password(plain: str) -> str:
    if not settings.DB_ENCRYPTION_KEY:
        return plain
    from cryptography.fernet import Fernet

    return Fernet(settings.DB_ENCRYPTION_KEY.encode()).encrypt(plain.encode()).decode()


def _config_from_row(tenant_id: str, row: Dict[str, Any], password: str) -> TenantSourceConfig:
    source_type = normalize_source_type(row["source_type"])
    port = row["mysql_port"]
    if port is None:
        port = 5432 if source_type == "postgres" else 3306
    return TenantSourceConfig(
        tenant_id=tenant_id,
        source_type=source_type,
        host=row["mysql_host"],
        port=int(port),
        database=row["mysql_db"],
        user=row["mysql_user"],
        password=password,
    )


def test_source_config(config: TenantSourceConfig) -> Dict[str, Any]:
    """Open a short-lived connection and run SELECT 1."""
    engine: Optional[Engine] = None
    try:
        engine = build_source_engine(config)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {
            "success": True,
            "message": (
                f"Connected to {config.source_type} "
                f"{config.user}@{config.host}:{config.port}/{config.database}"
            ),
        }
    except Exception as exc:
        logger.warning("Source connection test failed: %s", exc)
        return {"success": False, "message": str(exc)}
    finally:
        if engine is not None:
            engine.dispose()


def get_tenant_source(db: Session, tenant_id: str) -> Optional[Dict[str, Any]]:
    result = db.execute(text(_SELECT), {"tid": tenant_id})
    row = result.mappings().first()
    if not row:
        return None
    return dict(row)


def get_tenant_source_with_connection(
    db: Session, tenant_id: str
) -> Optional[Dict[str, Any]]:
    """Like get_tenant_source but also joins the DatabaseConnection name/engine."""
    result = db.execute(
        text(
            """
            SELECT
                tr.tenant_id, tr.display_name,
                COALESCE(tr.source_type, 'mysql') AS source_type,
                tr.mysql_host, tr.mysql_port, tr.mysql_db, tr.mysql_user,
                tr.mysql_password_enc, tr.is_active, tr.last_etl_at,
                tr.source_connection_id,
                dc.name  AS source_connection_name,
                dc.engine AS source_connection_engine
            FROM hrm_control.tenant_registry tr
            LEFT JOIN database_connections dc ON dc.id = tr.source_connection_id
            WHERE tr.tenant_id = :tid
            """
        ),
        {"tid": tenant_id},
    )
    row = result.mappings().first()
    if not row:
        return None
    return dict(row)


def set_source_connection_id(
    db: Session, tenant_id: str, connection_id: Optional[int]
) -> Dict[str, Any]:
    """Point a tenant's ETL source at a saved DatabaseConnection (or clear it)."""
    existing = get_tenant_source(db, tenant_id)
    if not existing:
        raise RuntimeError(
            f"Tenant '{tenant_id}' is not in tenant_registry. "
            "Add a source via POST /tenants/etl-sources/ first."
        )

    db.execute(
        text(
            "UPDATE hrm_control.tenant_registry SET source_connection_id = :cid WHERE tenant_id = :tid"
        ),
        {"cid": connection_id, "tid": tenant_id},
    )
    db.commit()
    row = get_tenant_source_with_connection(db, tenant_id)
    if not row:
        raise RuntimeError("Failed to reload tenant source after update")
    return row


def upsert_tenant_source(
    db: Session,
    tenant_id: str,
    *,
    display_name: str,
    source_type: str,
    mysql_host: str,
    mysql_port: Optional[int],
    mysql_db: str,
    mysql_user: str,
    mysql_password: Optional[str],
) -> Dict[str, Any]:
    st = normalize_source_type(source_type)
    default_port = 5432 if st == "postgres" else 3306
    port = mysql_port if mysql_port is not None else default_port

    existing = get_tenant_source(db, tenant_id)
    if mysql_password:
        pwd_enc = _encrypt_password(mysql_password)
    elif existing:
        pwd_enc = existing["mysql_password_enc"]
    else:
        raise ValueError("Password is required when registering a new source database")

    if existing:
        db.execute(
            text(
                """
                UPDATE hrm_control.tenant_registry SET
                    display_name = :dn,
                    source_type = :stype,
                    mysql_host = :host,
                    mysql_port = :port,
                    mysql_db = :db,
                    mysql_user = :user,
                    mysql_password_enc = :pwd,
                    is_active = TRUE
                WHERE tenant_id = :tid
                """
            ),
            {
                "tid": tenant_id,
                "dn": display_name,
                "stype": st,
                "host": mysql_host,
                "port": port,
                "db": mysql_db,
                "user": mysql_user,
                "pwd": pwd_enc,
            },
        )
    else:
        db.execute(
            text(
                """
                INSERT INTO hrm_control.tenant_registry
                    (tenant_id, display_name, source_type, mysql_host, mysql_port,
                     mysql_db, mysql_user, mysql_password_enc, is_active)
                VALUES (:tid, :dn, :stype, :host, :port, :db, :user, :pwd, TRUE)
                """
            ),
            {
                "tid": tenant_id,
                "dn": display_name,
                "stype": st,
                "host": mysql_host,
                "port": port,
                "db": mysql_db,
                "user": mysql_user,
                "pwd": pwd_enc,
            },
        )
    db.commit()
    row = get_tenant_source(db, tenant_id)
    if not row:
        raise RuntimeError("Failed to load tenant source after upsert")
    return row
