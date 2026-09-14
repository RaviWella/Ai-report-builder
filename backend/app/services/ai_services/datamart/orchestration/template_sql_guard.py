"""Deterministic guards for template SQL modifications."""
from __future__ import annotations

import sqlglot
from sqlglot import exp


def preserve_order_by_from_template(template_sql: str, modified_sql: str) -> tuple[str, bool]:
    def sort_col_key(e: exp.Expression) -> str:
        if isinstance(e, exp.Ordered):
            return e.this.sql(dialect="postgres").strip().lower()
        return e.sql(dialect="postgres").strip().lower()

    try:
        otree = sqlglot.parse_one(template_sql, dialect="postgres")
        mtree = sqlglot.parse_one(modified_sql, dialect="postgres")
    except Exception:
        return modified_sql, False

    o_ord = otree.find(exp.Order)
    m_ord = mtree.find(exp.Order)
    if not o_ord or not m_ord:
        return modified_sql, False

    orig_exprs = list(o_ord.expressions)
    mod_exprs = list(m_ord.expressions)
    if not orig_exprs or not mod_exprs:
        return modified_sql, False

    orig_keys = {sort_col_key(e) for e in orig_exprs}
    mod_keys = {sort_col_key(e) for e in mod_exprs}

    if orig_keys <= mod_keys:
        return modified_sql, False

    extra = [e for e in mod_exprs if sort_col_key(e) not in orig_keys]
    new_exprs = orig_exprs + extra
    merged_order = exp.Order(expressions=new_exprs)
    m_ord.replace(merged_order)

    try:
        out = mtree.sql(dialect="postgres")
    except Exception:
        return modified_sql, False

    if template_sql.strip().endswith(";") and not out.rstrip().endswith(";"):
        out = out.rstrip() + ";"
    return out, True
