#!/usr/bin/env python3
"""Quick diagnostic: app DB + tenant warehouse contents."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sqlalchemy import create_engine, text

from app.core.application_db import application_sync_url, build_url, connection_parts
from app.core.config import settings

app = create_engine(application_sync_url())
with app.connect() as c:
    tables = c.execute(
        text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'hrm_control' ORDER BY 1"
        )
    ).fetchall()
    print("APP hrm_control:", [t[0] for t in tables])
    try:
        ver = c.execute(text("SELECT version_num FROM alembic_version")).scalar()
        print("APP alembic:", ver)
    except Exception as e:
        print("APP alembic:", e)

parts = connection_parts(settings.application_database_url)
wh_url = build_url(
    host=parts["host"],
    port=int(parts["port"]),
    user=parts["user"],
    password=parts["password"],
    database="hrm_wh_demo_tenant",
    driver="psycopg2",
)
wh = create_engine(wh_url)
with wh.connect() as c:
    for schema in ("hr_raw", "hr", "hr_semantic", "hr_control", "public"):
        n = c.execute(
            text(
                "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = :s"
            ),
            {"s": schema},
        ).scalar()
        print(f"WH {schema} table count:", n)
    stg = c.execute(
        text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'hr_raw' AND table_name LIKE 'stg_%' ORDER BY 1"
        )
    ).fetchall()
    print("WH stg tables:", len(stg))
    for (name,) in stg[:5]:
        cnt = c.execute(text(f'SELECT COUNT(*) FROM hr_raw."{name}"')).scalar()
        print(f"  {name}: {cnt} rows")
    mart = c.execute(
        text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'hr' ORDER BY 1"
        )
    ).fetchall()
    print("WH hr mart:", [m[0] for m in mart])
    runs = c.execute(
        text(
            "SELECT run_id, status, rows_extracted, rows_loaded, left(error_message, 80) "
            "FROM hr_control.hr_etl_run_log ORDER BY run_id DESC LIMIT 5"
        )
    ).fetchall()
    print("Last ETL runs:")
    for r in runs:
        print(" ", r)
    steps = c.execute(
        text(
            "SELECT step_name, status, rows_processed, left(error_message, 60) "
            "FROM hr_control.hr_etl_step_log ORDER BY step_id DESC LIMIT 15"
        )
    ).fetchall()
    print("Recent steps:")
    for s in steps:
        print(" ", s)
