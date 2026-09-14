"""Distinct value lookup for runtime-filter dropdowns (read-only).

Builds `SELECT DISTINCT <col> FROM <entity table> WHERE <col> IS NOT NULL
ORDER BY 1 LIMIT n` through the same safe path as reports: parameterized,
tenant-scoped, SELECT-only. Used to populate viewer filter dropdowns (e.g. the
list of designations) without exposing physical schema.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from app.core.tenancy import TenantContext
from app.db.datamart import datamart_connection
from app.domain.semantic import SemanticCatalog
from app.query_engine import guards
from app.query_engine.sql_builder import TableRegistry


def distinct_values(
    *,
    ctx: TenantContext,
    datamart_key: str,
    catalog: SemanticCatalog,
    ref: str,
    limit: int = 500,
) -> list[Any]:
    # Resolve through the semantic layer (raises if unknown — never free-form).
    field = catalog.resolve(ref)
    entity = catalog.entity_of_ref(ref)

    registry = TableRegistry()
    col = registry.col_for(field.physical, entity.base_schema)

    stmt = (
        select(col).distinct().where(col.isnot(None)).order_by(col).limit(min(limit, 1000))
    )
    sql = str(stmt.compile(dialect=postgresql.dialect()))
    guards.assert_select_only(sql)

    with datamart_connection(ctx, datamart_key) as conn:
        rows = conn.execute(stmt).fetchall()
    return [r[0] for r in rows]
