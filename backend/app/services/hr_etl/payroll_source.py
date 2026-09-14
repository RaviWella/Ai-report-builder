"""Helpers for optional MintHRM payroll source tables (schema may vary by deployment)."""
from __future__ import annotations

import logging
from collections.abc import Callable

from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger("hr_etl.payroll_source")


def source_table_exists(engine: Engine, table_name: str) -> bool:
    """Return True if table exists in the connected source database."""
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT COUNT(*) AS n
                FROM information_schema.tables
                WHERE LOWER(table_name) = LOWER(:tbl)
                """
            ),
            {"tbl": table_name},
        ).mappings().first()
    return bool(row and row["n"] > 0)


def source_columns_exist(engine: Engine, table_name: str, *columns: str) -> bool:
    """True when every named column exists on the table in the current database."""
    if not columns:
        return True
    needed = {c.lower() for c in columns}
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT LOWER(column_name) AS column_name
                FROM information_schema.columns
                WHERE LOWER(table_name) = LOWER(:tbl)
                  AND table_schema = DATABASE()
                """
            ),
            {"tbl": table_name},
        ).fetchall()
    found = {r[0] for r in rows}
    missing = needed - found
    if missing:
        logger.info(
            "Table %s missing column(s) %s (found %d/%d required)",
            table_name,
            sorted(missing),
            len(needed) - len(missing),
            len(needed),
        )
        return False
    return True


def optional_extractor(
    table: str,
    fn: Callable[..., int],
    *required_columns: str,
) -> Callable[..., int]:
    """Skip extract when the table or expected MintHRM columns are absent."""

    def _wrapped(source: Engine, pg: Engine, tenant_id: str, *, incremental: bool = False) -> int:
        if not source_table_exists(source, table):
            logger.info("Skipping %s — table %s not found", fn.__name__, table)
            return 0
        if required_columns and not source_columns_exist(source, table, *required_columns):
            logger.info(
                "Skipping %s — table %s missing required column(s)",
                fn.__name__,
                table,
            )
            return 0
        return fn(source, pg, tenant_id, incremental=incremental)

    return _wrapped
