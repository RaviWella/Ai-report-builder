"""Verify Alembic heads, datamart tables, and app DB connectivity for v1.5."""
from __future__ import annotations

import sys

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

from app.core.application_db import create_postgres_engine, postgres_sync_url

load_dotenv()

EXPECTED_DATAMART = (
    "datamart_session_groups",
    "datamart_template_groups",
    "datamart_chat_sessions",
    "datamart_chat_messages",
    "datamart_chat_summaries",
    "datamart_templates",
    "datamart_template_versions",
)

EXPECTED_HEADS = {"0007", "dm_public_consolidate_001"}


def inspect_sync_db(host: str, port: int, database: str) -> dict:
    url = f"postgresql+psycopg2://postgres:postgres@{host}:{port}/{database}"
    result = {
        "database": database,
        "reachable": False,
        "datamart_tables": [],
        "missing_datamart": [],
        "alembic_versions": [],
        "hrm_control_table_count": 0,
        "error": None,
    }
    try:
        eng = create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 3})
        with eng.connect() as conn:
            result["reachable"] = True
            result["datamart_tables"] = [
                r[0]
                for r in conn.execute(
                    text(
                        """
                        SELECT table_name
                        FROM information_schema.tables
                        WHERE table_schema = 'public'
                          AND table_name LIKE 'datamart_%'
                        ORDER BY table_name
                        """
                    )
                )
            ]
            result["missing_datamart"] = [
                t for t in EXPECTED_DATAMART if t not in result["datamart_tables"]
            ]
            if conn.execute(
                text(
                    "SELECT 1 FROM information_schema.tables "
                    "WHERE table_schema = 'public' AND table_name = 'alembic_version'"
                )
            ).scalar():
                result["alembic_versions"] = [
                    r[0]
                    for r in conn.execute(
                        text("SELECT version_num FROM alembic_version ORDER BY 1")
                    )
                ]
            result["hrm_control_table_count"] = conn.execute(
                text(
                    """
                    SELECT count(*)
                    FROM information_schema.tables
                    WHERE table_schema = 'hrm_control'
                    """
                )
            ).scalar() or 0
        eng.dispose()
    except Exception as exc:
        result["error"] = str(exc)
    return result


def test_app_url() -> tuple[bool, str]:
    from app.core.config import settings

    url = postgres_sync_url(settings.application_database_url)
    try:
        eng = create_postgres_engine(url)
        with eng.connect() as conn:
            db = conn.execute(text("SELECT current_database()")).scalar()
            conn.execute(text("SELECT 1 FROM datamart_chat_sessions LIMIT 1"))
        eng.dispose()
        return True, f"sync OK on database={db!r} url={url}"
    except Exception as exc:
        return False, f"sync FAILED url={url}: {exc}"


def main() -> int:
    from app.core.config import settings

    print("=== v1.5 DB / migration verification ===\n")
    print(f"APPLICATION_DATABASE_URL: {settings.application_database_url}")
    print(f"APP_DATABASE_NAME:        {settings.APP_DATABASE_NAME}")
    if settings.APP_DATABASE_NAME not in settings.application_database_url:
        print(
            "WARNING: APP_DATABASE_NAME does not match the database in "
            "APPLICATION_DATABASE_URL. Migrations and the running API use the URL "
            "database (not APP_DATABASE_NAME alone).\n"
        )

    host, port = "localhost", 5438
    for db in ("hrm_analytics", "hrm_platform"):
        r = inspect_sync_db(host, port, db)
        print(f"--- {db} @ {host}:{port} ---")
        if r["error"]:
            print(f"  unreachable: {r['error']}")
            continue
        print(f"  alembic_version: {r['alembic_versions']}")
        print(f"  hrm_control tables: {r['hrm_control_table_count']}")
        print(f"  datamart tables ({len(r['datamart_tables'])}): {r['datamart_tables']}")
        if r["missing_datamart"]:
            print(f"  MISSING datamart: {r['missing_datamart']}")

    configured = inspect_sync_db(
        host,
        port,
        settings.application_database_url.split("/")[-1].split("?")[0],
    )
    heads = set(configured.get("alembic_versions") or [])
    missing_heads = EXPECTED_HEADS - heads
    extra_heads = heads - EXPECTED_HEADS

    print("\n--- configured app DB (from .env) ---")
    if missing_heads:
        print(f"  MISSING migration heads: {sorted(missing_heads)}")
    if extra_heads:
        print(f"  extra alembic rows: {sorted(extra_heads)}")
    if configured["missing_datamart"]:
        print(f"  MISSING tables: {configured['missing_datamart']}")
        return 1

    ok, msg = test_app_url()
    print(f"\n{msg}")
    if not ok:
        return 1
    if missing_heads:
        print("\nRun: cd backend && python -m alembic upgrade heads")
        return 1

    print("\nOK: both Alembic heads applied; datamart tables present; sync connection works.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
