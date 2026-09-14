"""Shared idempotent checks for Alembic migrations (partial / init_db bootstrap)."""
from __future__ import annotations

from sqlalchemy.engine import Connection, Engine
from sqlalchemy import inspect


def _inspector(bind: Connection | Engine):
    return inspect(bind)


def has_table(bind: Connection | Engine, schema: str | None, name: str) -> bool:
    return name in _inspector(bind).get_table_names(schema=schema)


def table_columns(bind: Connection | Engine, schema: str | None, table: str) -> set[str]:
    if not has_table(bind, schema, table):
        return set()
    return {c["name"] for c in _inspector(bind).get_columns(table, schema=schema)}


def has_index(
    bind: Connection | Engine, schema: str | None, table: str, index_name: str
) -> bool:
    if not has_table(bind, schema, table):
        return False
    return any(
        i.get("name") == index_name
        for i in _inspector(bind).get_indexes(table, schema=schema)
    )
