#!/usr/bin/env python
"""
Point demo_tenant at a local or env-configured hrm_wh_* warehouse in tenant_registry.

Usage (from backend/):
  python tools/seed_demo_tenant_registry_warehouse.py
  python tools/seed_demo_tenant_registry_warehouse.py --tenant-id demo_tenant --warehouse-db hrm_wh_demo_tenant
"""
from __future__ import annotations

import argparse
import os
import sys

_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(_BACKEND, ".env"))
except ImportError:
    pass

from sqlalchemy import create_engine, text

from app.core.application_db import application_sync_url, connection_parts
from app.core.config import settings
from app.services.ai_services.datamart import config as dm_config


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed demo_tenant warehouse in tenant_registry")
    parser.add_argument("--tenant-id", default=dm_config.DATAMART_DEFAULT_TENANT_ID)
    parser.add_argument("--warehouse-db", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--local",
        action="store_true",
        help="Point warehouse at localhost app Postgres (hrm_wh_* on :5438)",
    )
    args = parser.parse_args()

    tid = args.tenant_id.strip()
    wh_db = (args.warehouse_db or dm_config.WAREHOUSE_DB or "").strip()
    if not wh_db.startswith((settings.WAREHOUSE_DB_PREFIX or "hrm_wh_")):
        wh_db = f"{settings.WAREHOUSE_DB_PREFIX or 'hrm_wh_'}{tid}"

    parts = connection_parts(application_sync_url())
    if args.local:
        host = parts["host"]
        port = int(parts["port"])
    else:
        host = (dm_config.WAREHOUSE_HOST or settings.WAREHOUSE_DEFAULT_HOST or parts["host"]).strip()
        port = int(dm_config.WAREHOUSE_PORT or settings.WAREHOUSE_DEFAULT_PORT or parts["port"])

    url = application_sync_url()
    engine = create_engine(url, pool_pre_ping=True)

    with engine.begin() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM hrm_control.tenant_registry WHERE tenant_id = :tid"),
            {"tid": tid},
        ).scalar()
        if not exists:
            if args.dry_run:
                print(f"[dry-run] Would INSERT tenant_registry row for {tid}")
            else:
                conn.execute(
                    text(
                        """
                        INSERT INTO hrm_control.tenant_registry
                            (tenant_id, display_name, source_type, mysql_host, mysql_port,
                             mysql_db, mysql_user, mysql_password_enc, is_active)
                        VALUES
                            (:tid, :dn, 'mysql', '127.0.0.1', 3306,
                             'minthrm_demo', 'demo', 'demo', TRUE)
                        """
                    ),
                    {"tid": tid, "dn": f"{tid} (local)"},
                )
                print(f"tenant_registry: inserted minimal row for {tid}")

        if args.dry_run:
            print(f"[dry-run] Would set warehouse_db={wh_db!r} host={host} port={port} for {tid}")
            return

        conn.execute(
            text(
                """
                UPDATE hrm_control.tenant_registry
                SET warehouse_host = :host,
                    warehouse_port = :port,
                    warehouse_db = :whdb,
                    warehouse_user = COALESCE(NULLIF(warehouse_user, ''), :whuser),
                    updated_at = NOW()
                WHERE tenant_id = :tid
                """
            ),
            {
                "tid": tid,
                "host": host,
                "port": port,
                "whdb": wh_db,
                "whuser": dm_config.WAREHOUSE_USER or parts["user"],
            },
        )
    print(f"tenant_registry: {tid} -> warehouse_db={wh_db} ({host}:{port})")


if __name__ == "__main__":
    main()
