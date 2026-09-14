"""Register or update tenant source connection in hrm_control.tenant_registry.

Set in backend/.env (gitignored):

  MYSQL_EXTRACTOR_PROFILE=minthrm
  SOURCE_TYPE=mysql          # or postgres
  SOURCE_HOST=...            # or MYSQL_HOST
  SOURCE_PORT=3306           # 5432 for postgres
  SOURCE_DB=...
  SOURCE_USER=...
  SOURCE_PASSWORD=...
  MYSQL_TENANT_ID=demo_tenant
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import settings  # noqa: E402
from app.core.warehouse import (  # noqa: E402
    default_warehouse_db_name,
    ensure_warehouse_ready_sync,
    get_warehouse_engine_sync,
)
from app.services.hr_etl.source_connection import normalize_source_type  # noqa: E402


async def main() -> None:
    tid = settings.MYSQL_TENANT_ID or "demo_tenant"
    source_type = normalize_source_type(settings.etl_source_type)
    host = settings.etl_source_host
    db = settings.etl_source_db
    user = settings.etl_source_user
    password = settings.etl_source_password
    port = settings.etl_source_port

    if not all([host, db, user, password]):
        print(
            "Set SOURCE_HOST (or MYSQL_HOST), SOURCE_DB, SOURCE_USER, "
            "SOURCE_PASSWORD in backend/.env"
        )
        sys.exit(1)

    pwd_stored = password
    if settings.DB_ENCRYPTION_KEY:
        from cryptography.fernet import Fernet

        f = Fernet(settings.DB_ENCRYPTION_KEY.encode())
        pwd_stored = f.encrypt(password.encode()).decode()

    engine = create_async_engine(settings.platform_database_url)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                ALTER TABLE hrm_control.tenant_registry
                    ADD COLUMN IF NOT EXISTS source_type VARCHAR(16) NOT NULL DEFAULT 'mysql'
                """
            )
        )
        await conn.execute(
            text(
                """
                INSERT INTO hrm_control.tenant_registry
                    (tenant_id, display_name, source_type, mysql_host, mysql_port,
                     mysql_db, mysql_user, mysql_password_enc, warehouse_db, is_active)
                VALUES
                    (:tid, :dn, :stype, :host, :port, :db, :user, :pwd, :whdb, TRUE)
                ON CONFLICT (tenant_id) DO UPDATE SET
                    display_name = EXCLUDED.display_name,
                    source_type = EXCLUDED.source_type,
                    mysql_host = EXCLUDED.mysql_host,
                    mysql_port = EXCLUDED.mysql_port,
                    mysql_db = EXCLUDED.mysql_db,
                    mysql_user = EXCLUDED.mysql_user,
                    mysql_password_enc = EXCLUDED.mysql_password_enc,
                    warehouse_db = EXCLUDED.warehouse_db,
                    is_active = TRUE
                """
            ),
            {
                "tid": tid,
                "dn": f"MintHRM ({db})",
                "stype": source_type,
                "host": host,
                "port": port,
                "db": db,
                "user": user,
                "pwd": pwd_stored,
                "whdb": default_warehouse_db_name(tid),
            },
        )
    await engine.dispose()
    wh = get_warehouse_engine_sync(tid, provision=True)
    try:
        ensure_warehouse_ready_sync(wh, tid)
    finally:
        wh.dispose()
    print(
        f"Registered tenant '{tid}' source={source_type} -> "
        f"{user}@{host}:{port}/{db}"
    )
    print(f"Warehouse database: {default_warehouse_db_name(tid)}")
    print(f"Extractor profile: {settings.MYSQL_EXTRACTOR_PROFILE}")


if __name__ == "__main__":
    asyncio.run(main())
