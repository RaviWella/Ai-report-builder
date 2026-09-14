"""Provision tenants in hrm_control.tenant_registry without customer source DB credentials.

Source databases are configured after login via the UI into
hrm_control.tenant_etl_sources (same management database).
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.warehouse import (
    default_warehouse_db_name,
    get_platform_engine_sync,
    invalidate_tenant_cache,
)

_PROVISION_SQL = """
    INSERT INTO hrm_control.tenant_registry
        (tenant_id, display_name, source_type,
         mysql_host, mysql_port, mysql_db, mysql_user, mysql_password_enc,
         warehouse_db, is_active)
    VALUES
        (:tid, :dn, 'mysql', NULL, NULL, NULL, NULL, NULL, :whdb, TRUE)
    ON CONFLICT (tenant_id) DO UPDATE SET
        display_name = EXCLUDED.display_name,
        warehouse_db = COALESCE(
            NULLIF(hrm_control.tenant_registry.warehouse_db, ''),
            EXCLUDED.warehouse_db
        ),
        mysql_host = NULL,
        mysql_port = NULL,
        mysql_db = NULL,
        mysql_user = NULL,
        mysql_password_enc = NULL,
        source_connection_id = NULL,
        is_active = TRUE
    RETURNING (xmax = 0) AS inserted
"""


def provision_tenant_minimal_sync(
    tenant_id: str,
    *,
    display_name: Optional[str] = None,
    warehouse_db: Optional[str] = None,
) -> bool:
    """Sync provision for HRIS launch and scripts. Returns True if inserted."""
    tid = tenant_id.strip()
    dn = (display_name or tid).strip()
    whdb = (warehouse_db or "").strip() or default_warehouse_db_name(tid)
    eng = get_platform_engine_sync()
    with eng.begin() as conn:
        row = conn.execute(
            text(_PROVISION_SQL),
            {"tid": tid, "dn": dn, "whdb": whdb},
        ).mappings().first()
    invalidate_tenant_cache(tid)
    return bool(row and row.get("inserted"))


def provision_tenant_minimal(
    db: Session,
    tenant_id: str,
    *,
    display_name: Optional[str] = None,
    warehouse_db: Optional[str] = None,
) -> bool:
    """
    Insert or reactivate a tenant registry row (identity + warehouse routing only).

    Returns True if a new row was inserted, False if an existing row was updated.
    """
    tid = tenant_id.strip()
    dn = (display_name or tid).strip()
    whdb = (warehouse_db or "").strip() or default_warehouse_db_name(tid)

    result = db.execute(
        text(_PROVISION_SQL),
        {"tid": tid, "dn": dn, "whdb": whdb},
    )
    db.commit()
    invalidate_tenant_cache(tid)
    row = result.mappings().first()
    return bool(row and row.get("inserted"))
