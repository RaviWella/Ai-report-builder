"""
Ensure generated SQL only references tables present in the schema link packet.
"""
from __future__ import annotations

from ..schema_broker import SchemaGrounding
from ..sql.sql_refs import warehouse_table_names_from_sql


def tables_outside_link(sql: str, grounding: SchemaGrounding) -> list[str]:
    """Return unqualified table names in SQL that are not in the grounded allowlist."""
    if not sql or not grounding.columns_by_table:
        return []
    allowed = {t.lower() for t in grounding.table_short_names}
    used = warehouse_table_names_from_sql(sql)
    return [t for t in used if t.lower() not in allowed]


def assert_sql_tables_in_link(sql: str, grounding: SchemaGrounding) -> str | None:
    """Error message when SQL references tables outside the link; else None."""
    extra = tables_outside_link(sql, grounding)
    if not extra:
        return None
    allowed_preview = ", ".join(grounding.table_short_names[:8])
    return (
        f"SQL references tables not in schema link: {', '.join(extra)}. "
        f"Allowed: {allowed_preview}"
    )
