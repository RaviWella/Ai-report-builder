#!/usr/bin/env python3
"""Print recent hr_etl_run_log rows for a tenant warehouse."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, text

from app.core.application_db import build_url, connection_parts
from app.core.config import settings

tenant_id = sys.argv[1] if len(sys.argv) > 1 else "demo_tenant"
parts = connection_parts(settings.application_database_url)
db = f"hrm_wh_{tenant_id}"
wh_url = build_url(
    host=parts["host"],
    port=int(parts["port"]),
    user=parts["user"],
    password=parts["password"],
    database=db,
    driver="psycopg2",
)
wh = create_engine(wh_url)
with wh.connect() as c:
    print(f"Database: {db}\n")
    for row in c.execute(
        text(
            """
            SELECT run_id, run_type, status, started_at, completed_at,
                   rows_extracted, rows_loaded, triggered_by,
                   left(coalesce(error_message, ''), 100) AS err
            FROM hr_control.hr_etl_run_log
            ORDER BY run_id DESC
            LIMIT 15
            """
        )
    ).fetchall():
        print(row)
    print("\nRunning:")
    for row in c.execute(
        text(
            "SELECT run_id, run_type, started_at FROM hr_control.hr_etl_run_log "
            "WHERE status = 'running' ORDER BY started_at DESC"
        )
    ).fetchall():
        print(row)
