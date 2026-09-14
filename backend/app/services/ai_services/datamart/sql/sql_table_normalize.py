"""Normalize mistaken database.schema.table qualifiers before execute / binding."""
from __future__ import annotations

import logging
from typing import Optional

import sqlglot
from sqlglot import exp

from ..workspace.runtime_context import get_datamart_context

logger = logging.getLogger("ai_services.datamart.sql_normalize")


def _database_name_lower() -> Optional[str]:
    ctx = get_datamart_context()
    if ctx is None:
        return None
    name = (ctx.database_name or "").strip().lower()
    return name or None


def strip_database_catalog_prefix(sql: str) -> str:
    """
    Remove a leading database/catalog segment when the LLM emits
    ``{database}.hr.table`` while already connected to that database.

    PostgreSQL only accepts ``schema.table`` in-session.
    """
    db_name = _database_name_lower()
    if not db_name or not sql or not sql.strip():
        return sql

    try:
        tree = sqlglot.parse_one(sql, dialect="postgres")
    except Exception:  # noqa: BLE001
        return sql

    changed = False
    for table in tree.find_all(exp.Table):
        catalog = (table.catalog or "").strip().lower()
        if not catalog or catalog != db_name:
            continue
        schema = (table.db or "").strip()
        short = (table.name or "").strip()
        if not schema or not short:
            continue
        table.set("catalog", None)
        changed = True

    if not changed:
        return sql

    out = tree.sql(dialect="postgres")
    logger.info("Stripped database catalog prefix %r from SQL", db_name)
    return out


def binding_error_for_database_catalog(sql: str) -> Optional[str]:
    """Return a binding-style error if SQL uses database.schema.table."""
    db_name = _database_name_lower()
    if not db_name:
        return None
    try:
        tree = sqlglot.parse_one(sql, dialect="postgres")
    except Exception:  # noqa: BLE001
        return None

    for table in tree.find_all(exp.Table):
        catalog = (table.catalog or "").strip().lower()
        if catalog == db_name:
            short = (table.name or "table").strip()
            schema = (table.db or "schema").strip()
            return (
                f"Table qualifier '{catalog}.{schema}.{short}' is invalid: do not prefix "
                f"with the database name '{catalog}'. Use schema.table only "
                f"(e.g. {schema}.{short})."
            )
    return None


def rewrite_semantic_view_schema(sql: str) -> str:
    """
    Map ``hr.vw_*`` → ``{primary_schema}.vw_*`` for tenant ETL warehouses.

    Semantic summary views live in ``hr_semantic`` while mart/dim tables stay in ``hr``.
    """
    ctx = get_datamart_context()
    if ctx is None or not ctx.is_tenant_etl:
        return sql
    semantic = (ctx.primary_schema or "").strip()
    if not semantic or semantic.lower() in ("hr", ""):
        return sql
    if not sql or not sql.strip():
        return sql

    try:
        tree = sqlglot.parse_one(sql, dialect="postgres")
    except Exception:  # noqa: BLE001
        return sql

    changed = False
    for table in tree.find_all(exp.Table):
        schema = (table.db or "").strip().lower()
        short = (table.name or "").strip().lower()
        if schema == "hr" and short.startswith("vw_"):
            table.set("db", exp.to_identifier(semantic))
            changed = True

    if not changed:
        return sql
    out = tree.sql(dialect="postgres")
    logger.info("Rewrote hr.vw_* tables to %s.vw_* for warehouse execute", semantic)
    return out
