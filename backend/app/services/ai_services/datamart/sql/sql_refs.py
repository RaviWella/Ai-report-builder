"""SQL reference helpers (table names from SQL text)."""
from __future__ import annotations

import sqlglot
from sqlglot import exp

from ..workspace.runtime_context import get_datamart_context


def _allowed_schemas_lower() -> frozenset[str]:
    ctx = get_datamart_context()
    if ctx is not None:
        return ctx.allowed_schemas_lower
    from ..config import allowed_schemas_lower_static

    return allowed_schemas_lower_static()


def _cte_names_from_tree(tree: exp.Expression) -> set[str]:
    names: set[str] = set()
    for cte in tree.find_all(exp.CTE):
        alias = (cte.alias_or_name or "").strip().lower()
        if alias:
            names.add(alias)
    return names


def warehouse_table_names_from_sql(sql: str) -> list[str]:
    """
    Distinct unqualified table names referenced in ``sql`` for allowed schemas.
    """
    allowed = _allowed_schemas_lower()
    out: list[str] = []
    seen: set[str] = set()
    try:
        tree = sqlglot.parse_one(sql, dialect="postgres")
    except Exception:
        return []
    cte_names = _cte_names_from_tree(tree)
    for node in tree.find_all(exp.Table):
        tname = node.name
        if not tname:
            continue
        if (tname or "").lower() in cte_names:
            continue
        db = (node.db or "").strip().lower()
        if db and db not in allowed:
            continue
        key = tname.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(tname)
        if len(out) >= 40:
            break
    return out


def warehouse_introspection_keys_from_sql(sql: str) -> list[str]:
    """
    Schema-qualified ``schema.table`` keys when SQL specifies a schema; else short names.

    Used for warehouse introspection so ``hr.vw_payroll_summary`` resolves to the ``hr``
    view (not the first ``hr_semantic`` match from short-name lookup).
    """
    allowed = _allowed_schemas_lower()
    out: list[str] = []
    seen: set[str] = set()
    try:
        tree = sqlglot.parse_one(sql, dialect="postgres")
    except Exception:
        return warehouse_table_names_from_sql(sql)
    cte_names = _cte_names_from_tree(tree)
    for node in tree.find_all(exp.Table):
        tname = (node.name or "").strip()
        if not tname:
            continue
        if tname.lower() in cte_names:
            continue
        db = (node.db or "").strip().lower()
        if db and db not in allowed:
            continue
        if db:
            key = f"{db}.{tname}".lower()
            token = f"{db}.{tname}"
        else:
            key = tname.lower()
            token = tname
        if key in seen:
            continue
        seen.add(key)
        out.append(token)
        if len(out) >= 40:
            break
    return out
