"""Physical SQL construction helpers using SQLAlchemy Core (D5).

A `TableRegistry` builds exactly ONE lightweight `table()` clause per physical
(schema, table) and reuses it for every column reference. This is essential: if a
fresh table object were created per column, SQLAlchemy would treat each as a
distinct FROM and silently add cartesian products. Physical names come ONLY from
the semantic catalogue — never from user/AI input.
"""

from __future__ import annotations

from sqlalchemy import Column, column, table
from sqlalchemy.sql.elements import ColumnClause, ColumnElement
from sqlalchemy.sql.selectable import TableClause

from app.domain.semantic import Entity, PhysicalColumn, SemanticCatalog


class TableRegistry:
    """One table clause per (schema, table); columns added on demand."""

    def __init__(self) -> None:
        self._tables: dict[tuple[str, str], TableClause] = {}
        self._cols: dict[tuple[str, str], set[str]] = {}

    def _key(self, schema: str, name: str) -> tuple[str, str]:
        return (schema, name)

    def table_for(self, schema: str, name: str, columns: set[str]) -> TableClause:
        key = self._key(schema, name)
        if key not in self._tables:
            self._cols[key] = set(columns)
            self._tables[key] = table(name, *(Column(c) for c in sorted(columns)), schema=schema)
        else:
            missing = columns - self._cols[key]
            if missing:
                # Rebuild with the union of columns (table clauses are immutable-ish).
                self._cols[key] |= missing
                self._tables[key] = table(
                    name, *(Column(c) for c in sorted(self._cols[key])), schema=schema
                )
        return self._tables[key]

    def get(self, schema: str, name: str) -> TableClause:
        return self._tables[self._key(schema, name)]

    def col(self, schema: str, name: str, col_name: str) -> ColumnClause:
        return self.table_for(schema, name, {col_name}).c[col_name]

    def col_for(self, physical: PhysicalColumn, base_schema: str) -> ColumnElement:
        """A field's physical binding as a SQLAlchemy expression — the plain
        column, or (when `json_key` is set) that column's `->> key` extraction,
        the key bound as a parameter like every other filter/lookup value here
        (never string-built into SQL)."""
        schema = physical.schema_name or base_schema
        col = self.col(schema, physical.table, physical.column)
        if physical.json_key:
            return col.op("->>")(physical.json_key)
        return col


def collect_columns(catalog: SemanticCatalog, refs: set[str]) -> dict[tuple[str, str], set[str]]:
    """Compute the physical columns needed per (schema, table) for the given refs.

    Includes each ref's physical column. Caller adds entity PKs / join keys.
    """
    needed: dict[tuple[str, str], set[str]] = {}
    fidx = catalog.field_index()
    for ref in refs:
        if ref.startswith("calc."):
            continue
        field = fidx[ref]
        entity = catalog.entity_of_ref(ref)
        schema = field.physical.schema_name or entity.base_schema
        needed.setdefault((schema, field.physical.table), set()).add(field.physical.column)
    return needed


def entity_base(entity: Entity) -> tuple[str, str]:
    return (entity.base_schema, entity.base_table)


__all__ = ["TableRegistry", "collect_columns", "entity_base", "column"]
