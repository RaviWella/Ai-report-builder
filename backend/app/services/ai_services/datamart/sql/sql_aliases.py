"""Map SQL table aliases to physical table short names."""
from __future__ import annotations

import logging
import re

from sqlglot import exp
from sqlglot import parse_one as sqlglot_parse_one

from ..workspace.runtime_context import get_datamart_context, mart_schema_for_hints

logger = logging.getLogger("ai_services.datamart.sql_aliases")


def schema_pattern_for_sql() -> str:
    """Regex alternation of allowed mart schemas (for FROM/JOIN parsing)."""
    ctx = get_datamart_context()
    if ctx is not None and ctx.query_schemas:
        return "(?:" + "|".join(re.escape(s) for s in ctx.query_schemas) + ")"
    return re.escape(mart_schema_for_hints())


def _allowed_schemas_lower() -> frozenset[str] | None:
    ctx = get_datamart_context()
    if ctx is not None:
        return ctx.allowed_schemas_lower
    return None


def _alias_from_table_node(node: exp.Expression) -> tuple[str, str] | None:
    """Return (alias_lower, table_short_lower) from a FROM/JOIN table expression."""
    if isinstance(node, exp.Alias):
        alias = (node.alias or node.alias_or_name or "").strip()
        inner = node.this
    elif isinstance(node, exp.Table):
        alias = (node.alias or node.name or "").strip()
        inner = node
    else:
        return None

    if not isinstance(inner, exp.Table) or not inner.name:
        return None
    if not alias:
        alias = inner.name

    schema = (inner.db or "").strip().lower()
    allowed = _allowed_schemas_lower()
    if allowed and schema and schema not in allowed:
        return None

    return alias.lower(), inner.name.lower()


def _alias_to_table_short_sqlglot(sql: str) -> dict[str, str]:
    tree = sqlglot_parse_one(sql, dialect="postgres")
    mapping: dict[str, str] = {}
    for from_node in tree.find_all(exp.From):
        pair = _alias_from_table_node(from_node.this)
        if pair:
            mapping[pair[0]] = pair[1]
    for join in tree.find_all(exp.Join):
        pair = _alias_from_table_node(join.this)
        if pair:
            mapping[pair[0]] = pair[1]
    return mapping


def _alias_to_table_short_regex(sql: str) -> dict[str, str]:
    ctx = get_datamart_context()
    mapping: dict[str, str] = {}
    if ctx is not None and ctx.query_schemas:
        schema_pat = "(?:" + "|".join(re.escape(s) for s in ctx.query_schemas) + ")"
        pattern = rf"(?:FROM|JOIN)\s+{schema_pat}\.(\w+)\s+(?:AS\s+)?(\w+)\b"
        for m in re.finditer(pattern, sql, flags=re.IGNORECASE):
            mapping[m.group(2).lower()] = m.group(1).lower()
    else:
        for m in re.finditer(
            r"(?:FROM|JOIN)\s+(\w+)\.(\w+)\s+(?:AS\s+)?(\w+)\b",
            sql,
            flags=re.IGNORECASE,
        ):
            mapping[m.group(3).lower()] = m.group(2).lower()
    return mapping


def alias_to_table_short(sql: str) -> dict[str, str]:
    """Map SQL alias (lower) -> table short name (lower) from FROM/JOIN clauses."""
    try:
        return _alias_to_table_short_sqlglot(sql)
    except Exception as exc:  # noqa: BLE001
        logger.debug("sqlglot alias parse failed, using regex: %s", exc)
        return _alias_to_table_short_regex(sql)
