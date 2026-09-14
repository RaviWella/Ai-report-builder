"""List datamart_* tables in public schema (platform DB)."""
from __future__ import annotations

import os
import sys

from dotenv import load_dotenv
from sqlalchemy import text

from app.core.application_db import create_postgres_engine, postgres_sync_url

load_dotenv()

EXPECTED = (
    "datamart_session_groups",
    "datamart_template_groups",
    "datamart_chat_sessions",
    "datamart_chat_messages",
    "datamart_chat_summaries",
    "datamart_templates",
    "datamart_template_versions",
)


def main() -> int:
    url = postgres_sync_url(
        os.getenv(
            "APPLICATION_DATABASE_URL",
            "postgresql+psycopg2://postgres:postgres@localhost:5438/hrm_analytics",
        )
    )
    engine = create_postgres_engine(url)
    with engine.connect() as conn:
        result = conn.execute(
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
        tables = [row[0] for row in result.fetchall()]
    engine.dispose()

    missing = [t for t in EXPECTED if t not in tables]
    print("Found:", tables)
    if missing:
        print("Missing:", missing)
        return 1
    print("All expected datamart tables present.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
