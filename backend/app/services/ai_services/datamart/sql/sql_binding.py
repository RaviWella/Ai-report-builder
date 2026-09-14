"""
Validate generated SQL against a schema grounding allowlist (anti-hallucination).
"""
from __future__ import annotations

import logging
from typing import Optional

import sqlglot
from sqlglot import exp

from .. import config as dm_config
from ..config import allowed_schemas_lower_static, primary_schema_name
from ..workspace.runtime_context import get_datamart_context
from ..schema_broker import SchemaGrounding
from .sql_column_allowlist import allowed_columns_for_table, columns_by_table_short
from .sql_table_normalize import binding_error_for_database_catalog

logger = logging.getLogger("ai_services.datamart.binding")


def _select_output_aliases(tree: exp.Expression) -> set[str]:
    """Output column aliases from the outer SELECT (ORDER BY may reference these)."""
    aliases: set[str] = set()
    select = tree if isinstance(tree, exp.Select) else tree.find(exp.Select)
    if not select:
        return aliases
    for expr in select.expressions:
        alias = (expr.alias or "").strip().lower()
        if alias:
            aliases.add(alias)
    return aliases


def _allowed_schemas_lower() -> frozenset[str]:
    ctx = get_datamart_context()
    if ctx is not None:
        return ctx.allowed_schemas_lower
    return allowed_schemas_lower_static()


def _primary_schema_label() -> str:
    ctx = get_datamart_context()
    if ctx is not None:
        return ", ".join(ctx.query_schemas)
    return ", ".join(dm_config.parse_query_schemas())


def validate_sql_bindings(
    sql: str,
    grounding: SchemaGrounding,
) -> Optional[str]:
    """
    Return None if SQL only references allowed tables/columns; else an error message
    for the LLM repair pass.
    """
    if not grounding.columns_by_table:
        return None

    catalog_err = binding_error_for_database_catalog(sql)
    if catalog_err:
        return catalog_err

    allowed_schemas = _allowed_schemas_lower()
    allowed_tables = {q.lower() for q in grounding.qualified_tables}
    allowed_short = {q.rsplit(".", 1)[-1].lower() for q in grounding.qualified_tables}
    cols_by_short = columns_by_table_short(grounding)
    multi_table = len(grounding.table_short_names) >= 2
    strict_multi = dm_config.DATAMART_VALIDATION_STRICT_BINDING and multi_table

    try:
        tree = sqlglot.parse_one(sql, dialect="postgres")
    except Exception as exc:  # noqa: BLE001
        return f"SQL parse error during binding check: {exc}"

    output_aliases = _select_output_aliases(tree)

    cte_names: set[str] = set()
    cte_aliases: set[str] = set()
    for cte in tree.find_all(exp.CTE):
        alias = (cte.alias_or_name or "").strip().lower()
        if alias:
            cte_names.add(alias)

    subquery_aliases: set[str] = set()
    for sub in tree.find_all(exp.Subquery):
        alias = (sub.alias_or_name or "").strip().lower()
        if alias:
            subquery_aliases.add(alias)

    alias_to_table: dict[str, str] = {}
    for table in tree.find_all(exp.Table):
        short = (table.name or "").lower()
        if not short:
            continue
        if short in cte_names:
            alias = (table.alias_or_name or table.name or "").lower()
            cte_aliases.add(alias)
            if table.name:
                cte_aliases.add(table.name.lower())
            continue
        db = (table.db or "").strip().lower()
        if db and db not in allowed_schemas:
            return (
                f"Table '{table.db}.{table.name}' is outside allowed schemas "
                f"({_primary_schema_label()})."
            )
        if short in cte_names:
            continue
        if short not in allowed_short:
            return (
                f"Table '{table.name}' is not in the grounded allowlist. "
                f"Allowed tables: {', '.join(sorted(allowed_short))}."
            )
        if db:
            qualified = f"{db}.{short}"
        else:
            matches = [q for q in allowed_tables if q.endswith(f".{short}")]
            if len(matches) == 1:
                qualified = matches[0]
            else:
                ctx = get_datamart_context()
                primary = ctx.primary_schema if ctx else primary_schema_name()
                qualified = f"{primary}.{short}"
        alias = (table.alias_or_name or table.name or "").lower()
        alias_to_table[alias] = qualified
        if table.name:
            alias_to_table[table.name.lower()] = qualified

    for col in tree.find_all(exp.Column):
        col_name = (col.name or "").lower()
        if not col_name or col_name == "*":
            continue
        table_ref = (col.table or "").lower()
        if table_ref:
            if (
                table_ref in cte_aliases
                or table_ref in cte_names
                or table_ref in subquery_aliases
            ):
                continue
            qualified = alias_to_table.get(table_ref)
            if qualified:
                table_short = qualified.rsplit(".", 1)[-1].lower()
                allowed_on_table = cols_by_short.get(table_short, set())
                if col_name not in allowed_on_table:
                    hint = ""
                    if allowed_on_table:
                        sample = ", ".join(sorted(allowed_on_table)[:8])
                        hint = f" Allowed on {table_short}: {sample}."
                    return (
                        f"Column '{col.table}.{col.name}' is not in the allowlist for "
                        f"that table.{hint}"
                    )
            elif table_ref not in allowed_short:
                return f"Unknown table alias or name '{col.table}' in column reference."
        else:
            if col_name in output_aliases:
                continue
            referenced_shorts = {
                q.rsplit(".", 1)[-1].lower() for q in alias_to_table.values()
            }
            if not referenced_shorts:
                referenced_shorts = set(cols_by_short.keys())

            matching = [
                t
                for t in referenced_shorts
                if col_name in cols_by_short.get(t, set())
            ]
            if len(matching) == 0:
                tables_hint = ", ".join(sorted(referenced_shorts)[:6])
                return (
                    f"Column '{col.name}' is not on the table(s) used in this query "
                    f"({tables_hint}). Use only columns listed for that table in the "
                    "grounded schema — not names from other tables in the allowlist."
                )
            if len(matching) > 1 or strict_multi or len(referenced_shorts) > 1:
                return (
                    f"Column '{col.name}' must use a table alias when multiple tables "
                    f"are in scope ({', '.join(sorted(referenced_shorts))})."
                )

    return None
