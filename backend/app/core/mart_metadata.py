"""Per-tenant mart metadata tables (database_connections, data_access_rules)."""
from __future__ import annotations

import logging

from sqlalchemy import MetaData, inspect
from sqlalchemy.engine import Connection, Engine

from app.models.database_connection import DataAccessRule, DatabaseConnection

logger = logging.getLogger("mart_metadata")

MART_METADATA_MODELS = (DatabaseConnection, DataAccessRule)


def _table_exists(conn: Connection, schema: str, table_name: str) -> bool:
    return inspect(conn).has_table(table_name, schema=schema)


def ensure_mart_metadata_tables(conn: Connection, mart_schema: str) -> int:
    """Create connection/RLS tables in the tenant mart schema if missing."""
    missing = [
        model
        for model in MART_METADATA_MODELS
        if not _table_exists(conn, mart_schema, model.__tablename__)
    ]
    if not missing:
        return 0

    md = MetaData(schema=mart_schema)
    for model in MART_METADATA_MODELS:
        model.__table__.tometadata(md, schema=mart_schema, name=model.__tablename__)
    md.create_all(conn, checkfirst=True)
    logger.info(
        "Ensured mart metadata tables in %s: %s",
        mart_schema,
        ", ".join(m.__tablename__ for m in missing),
    )
    return len(missing)


def ensure_mart_metadata_tables_sync(engine: Engine, mart_schema: str) -> int:
    with engine.begin() as conn:
        return ensure_mart_metadata_tables(conn, mart_schema)
