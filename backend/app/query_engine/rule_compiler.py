"""Compile a RuleReportSpec into a single safe SQL SELECT (SRS §4.x).

Three layers, assembled as nested subqueries so aggregates and post-aggregate
metrics compose cleanly:

  rows  : SELECT grain, <source cols>, <day_value CASE> AS day_value  FROM source
  agg   : SELECT grain, <rollup aggregates, with FILTER for "… where …">  GROUP BY grain
  final : SELECT grain, <rollup cols>, <compute formulas over rollup + constants>

Every expression (case when/value, define, rollup inner/where, compute formula) is
compiled by the whitelisted rule_expr compiler — no raw SQL, no eval. A row-limit
guard is applied like the main compiler.
"""

from __future__ import annotations

import ast
import re

import datetime

from sqlalchemy import (
    Date, Numeric, Select, and_, bindparam, case, column, func, literal, select, table, true,
)
from sqlalchemy.sql.elements import ColumnElement

from app.core.config import settings
from app.domain.rule_report import RuleReportSpec
from app.query_engine import guards
from app.query_engine.rule_expr import compile_expr

_AGGS = {"sum", "avg", "count", "min", "max"}
# Function names are NOT source columns — exclude them when wiring the source table.
_FUNCTIONS = {"greatest", "least", "max", "min", "coalesce", "abs", "round", "sum", "avg", "count",
              "time", "hours_between"}


def _names(expr: str) -> set[str]:
    """Bare Name identifiers referenced in an expression (best-effort, for wiring)."""
    try:
        tree = ast.parse(expr or "", mode="eval")
    except SyntaxError:
        return set()
    return {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}


def _source_columns(spec: RuleReportSpec) -> list[str]:
    """Physical source columns the spec references (everything that isn't a
    constant, a define, a derived rollup/compute name, or day_value)."""
    # Reserved = per-row-scope names only (constants, defines, row_cases, day_value,
    # functions). NOT rollup/compute output names — those live in the aggregate scope,
    # so a rollup may legitimately be `sum(late_minutes) AS late_minutes` where
    # late_minutes is also the source column it reads.
    reserved = (set(spec.constants) | set(spec.day_value.define)
                | set(spec.row_cases) | _FUNCTIONS | {"day_value", "row_value"})
    used: set[str] = set(spec.grain) | {f.column for f in spec.filters if f.column}
    for c in spec.day_value.cases:
        used |= _names(c.when) | _names(c.value)
    for d in spec.day_value.define.values():
        used |= _names(d)
    if spec.day_value.else_value:
        used |= _names(spec.day_value.else_value)
    for block in spec.row_cases.values():       # extra per-row labels (day_category …)
        for c in block.cases:
            used |= _names(c.when) | _names(c.value)
        if block.else_value:
            used |= _names(block.else_value)
    for r in spec.rollup.values():
        expr, _, where = r.partition(" where ")
        inner = _agg_inner(expr)
        used |= _names(inner) | _names(where)
    return sorted(used - reserved)


def _phys(fqtn: str, cols: list[str], alias: str | None = None):
    """A physical table with the named columns; optionally aliased."""
    schema, _, tbl = fqtn.partition(".")
    t = table(tbl, *[column(c) for c in cols], schema=schema)
    return t.alias(alias) if alias else t


def _build_from(spec: RuleReportSpec, referenced: set[str]):
    """Build the row-level FROM and a flat {bare_col -> ColumnElement} map.

    Single-source: one table with the referenced columns.
    Multi-source: the first `sources` entry is the base (driving) table; each other
    attaches via its `join` — plain LEFT/INNER, or `left_pick_one` (a LEFT JOIN LATERAL
    keeping one row per base row by `priority`). Column names are unique across sources
    (validated in the spec), so expressions stay unqualified."""
    if not spec.sources:
        schema, _, tbl = spec.source.partition(".")
        need = {*spec.grain, *referenced}
        t = table(tbl, *[column(c) for c in need], schema=schema)
        return t, {c: t.c[c] for c in need}

    aliases = list(spec.sources)
    base_alias, *rest = aliases
    bdef = spec.sources[base_alias]
    base = _phys(bdef.table, bdef.columns, base_alias)
    from_clause = base

    # A column declared in >1 source is kept OUT of the flat namespace (ambiguous);
    # referencing it in an expression is a compile error (handled by the caller). Join
    # keys resolve structurally (base.c / inner.c) using the PHYSICAL name — always,
    # regardless of column_aliases — so they may safely be ambiguous. column_aliases
    # only affects the LOGICAL name a column is exposed under here, in the flat
    # namespace grain/filters/expressions actually reference.
    owners: dict[str, list[ColumnElement]] = {}
    for c in bdef.columns:
        owners.setdefault(bdef.column_aliases.get(c, c), []).append(base.c[c])

    for a in rest:
        d = spec.sources[a]
        j = d.join
        keys = j.keys()                                  # [(this_col, base_col), …]
        if j.type == "left_pick_one":
            inner = _phys(d.table, d.columns)            # unaliased inside the lateral
            conds = [inner.c[tc] == base.c[bc] for tc, bc in keys]
            p = j.priority
            whens = [(inner.c[p.column] == v, i) for i, v in enumerate(p.order)]
            order_by: list = [case(*whens, else_=len(p.order))]
            if p.tiebreak:
                tb = inner.c[p.tiebreak]
                # NULLS LAST both ways: a missing tiebreak value must never win the pick
                # (Postgres defaults DESC->NULLS FIRST, which would let a NULL win).
                ordered = tb.desc() if p.tiebreak_dir == "desc" else tb.asc()
                order_by.append(ordered.nulls_last())
            lat = (select(*[inner.c[c] for c in d.columns]).select_from(inner)
                   .where(*conds).order_by(*order_by).limit(1).lateral(a))
            from_clause = from_clause.join(lat, true(), isouter=True)
            attached = lat
        else:                                            # left | inner
            attached = _phys(d.table, d.columns, a)
            oncl = and_(*[attached.c[tc] == base.c[bc] for tc, bc in keys])
            from_clause = from_clause.join(attached, oncl, isouter=(j.type == "left"))
        for c in d.columns:
            owners.setdefault(d.column_aliases.get(c, c), []).append(attached.c[c])

    colmap = {c: els[0] for c, els in owners.items() if len(els) == 1}
    return from_clause, colmap


def _dep_order(exprs: dict[str, str]) -> list[str]:
    """Order a set of named expressions so each comes AFTER the peers it references.

    `define` and `compute` may reference earlier entries, but they are stored in a JSONB
    column that does NOT preserve key order — so we must recover the dependency order
    ourselves instead of trusting dict insertion order. Raises on a cyclic reference."""
    names = set(exprs)
    deps = {n: (_names(e) & names) - {n} for n, e in exprs.items()}
    order: list[str] = []
    done: set[str] = set()
    active: set[str] = set()

    def visit(n: str) -> None:
        if n in done:
            return
        if n in active:
            raise guards.GuardError(f"cyclic dependency among expressions at {n!r}")
        active.add(n)
        for d in deps[n]:
            visit(d)
        active.discard(n)
        done.add(n)
        order.append(n)

    for n in exprs:
        visit(n)
    return order


def _agg_inner(agg_expr: str) -> str:
    """'sum(day_value)' -> 'day_value'."""
    m = re.match(r"^\s*([a-z]+)\s*\((.*)\)\s*$", agg_expr.strip(), re.I | re.S)
    if not m or m.group(1).lower() not in _AGGS:
        raise guards.GuardError(f"rollup must be agg(expr): {agg_expr!r} (agg in {sorted(_AGGS)})")
    return m.group(2)


def _agg_fn(agg_expr: str):
    return re.match(r"^\s*([a-z]+)\s*\(", agg_expr.strip(), re.I).group(1).lower()


def _filter_value(ftype: str, val):  # noqa: ANN001, ANN202
    """Coerce a runtime filter value to match the column type, so the bound parameter
    isn't sent as a bare VARCHAR (Postgres won't compare `date >= varchar`)."""
    if isinstance(val, str):
        if ftype in ("date", "period"):
            return datetime.date.fromisoformat(val)
        if ftype == "number":
            return float(val) if ("." in val or "e" in val.lower()) else int(val)
    return val


def _filter_type(ftype: str):  # noqa: ANN202
    return {"date": Date(), "period": Date(), "number": Numeric()}.get(ftype)


def _apply_filters(sel: Select, colmap: dict, spec: RuleReportSpec, params: dict) -> Select:
    """Apply runtime filters at the per-row (source) level, before aggregation.
    Values are bound parameters; a missing/blank value simply isn't applied."""
    for f in spec.filters:
        if not f.column:
            continue
        val = params.get(f.name)
        if val is None or (isinstance(val, str) and not val.strip()):
            continue
        if f.column not in colmap:
            raise guards.GuardError(f"filter column not in any source: {f.column!r}")
        col = colmap[f.column]
        if f.op == "contains":
            sel = sel.where(col.ilike(bindparam(f.name, value=f"%{val}%")))
            continue
        bp = bindparam(f.name, value=_filter_value(f.type, val), type_=_filter_type(f.type))
        ops = {"eq": col.__eq__, "neq": col.__ne__, "gte": col.__ge__,
               "lte": col.__le__, "gt": col.__gt__, "lt": col.__lt__}
        if f.op not in ops:
            raise guards.GuardError(f"unsupported filter op: {f.op!r}")
        sel = sel.where(ops[f.op](bp))
    return sel


def compile_rule_report(spec: RuleReportSpec, params: dict | None = None) -> Select:
    consts: dict[str, object] = dict(spec.constants)
    src_cols = _source_columns(spec)

    # --- rows: per-row day_value over the source(s) ---
    from_clause, colmap = _build_from(spec, set(src_cols))
    missing = ({*spec.grain, *src_cols}) - set(colmap)
    if missing:
        # A referenced name is either undeclared, or declared in >1 source (ambiguous —
        # qualify it by keeping it in only one source's `columns`).
        declared = {c for s in spec.sources.values() for c in s.columns}
        ambig = sorted(m for m in missing if m in declared)
        undef = sorted(m for m in missing if m not in declared)
        parts = []
        if undef:
            parts.append(f"not found in any source: {undef}")
        if ambig:
            parts.append(f"ambiguous (declared in >1 source): {ambig}")
        raise guards.GuardError("; ".join(parts))

    ns: dict[str, object] = {**consts, **colmap}
    for name in _dep_order(spec.day_value.define):      # defines resolve in dependency order
        ns[name] = compile_expr(spec.day_value.define[name], ns)
    whens = [(compile_expr(c.when, ns), compile_expr(c.value, ns)) for c in spec.day_value.cases]
    else_ = compile_expr(spec.day_value.else_value, ns) if spec.day_value.else_value else literal(None)
    day_value = case(*whens, else_=else_)

    # extra per-row labels (e.g. day_category) — evaluated over the same namespace,
    # projected as row columns so rollup FILTER breakdowns can reference them.
    row_case_cols: dict[str, ColumnElement] = {}
    for cat_name, block in spec.row_cases.items():
        cwhens = [(compile_expr(c.when, ns), compile_expr(c.value, ns)) for c in block.cases]
        celse = compile_expr(block.else_value, ns) if block.else_value else literal(None)
        row_case_cols[cat_name] = case(*cwhens, else_=celse)

    rows_sel = select(
        *[colmap[g].label(g) for g in spec.grain],
        *[colmap[c].label(c) for c in src_cols if c not in spec.grain],
        day_value.label("day_value"),
        *[col.label(name) for name, col in row_case_cols.items()],
    ).select_from(from_clause)
    rows_sel = _apply_filters(rows_sel, colmap, spec, params or {})
    rows = rows_sel.subquery("rows")

    # --- agg: rollup aggregates over grain ---
    row_ns: dict[str, object] = {**consts, **{c.name: c for c in rows.c}}
    if "day_value" in row_ns:            # the per-row value is referable as either name
        row_ns.setdefault("row_value", row_ns["day_value"])
    agg_cols: list[ColumnElement] = []
    for name, rexpr in spec.rollup.items():
        expr_part, _, where_part = rexpr.partition(" where ")
        fn_name = _agg_fn(expr_part)
        inner = compile_expr(_agg_inner(expr_part), row_ns)
        agg = getattr(func, fn_name)(inner)
        if where_part.strip():
            agg = agg.filter(compile_expr(where_part, row_ns))
        if fn_name in ("sum", "count"):
            # SUM/COUNT over a group with zero matching rows (most often a
            # `where` FILTER that a particular grain-group never satisfies)
            # returns SQL NULL, not 0 — which then silently poisons any
            # `compute`/`having` that adds or compares it (NULL propagates
            # through arithmetic, and `NULL > 0` is never true). 0 is the
            # only sensible "nothing matched" value for a running total or
            # count; avg/min/max are left alone since 0 isn't a safe default
            # for them (an average or a min/max of nothing isn't 0).
            agg = func.coalesce(agg, 0)
        agg_cols.append(agg.label(name))
    agg = select(*[rows.c[g].label(g) for g in spec.grain], *agg_cols) \
        .group_by(*[rows.c[g] for g in spec.grain]).subquery("agg")

    # --- final: compute over the aggregates (+ constants), in dependency order ---
    out_ns: dict[str, object] = {**consts, **{c.name: c for c in agg.c}}
    for name in _dep_order(spec.compute):            # compute resolves in dependency order
        out_ns[name] = compile_expr(spec.compute[name], out_ns)

    # filters marked expose_as also project their runtime value as a constant
    # output column (e.g. show the chosen "to" date as an "End date" column) —
    # the same bound value used to filter, not a second concept.
    exposed = {f.expose_as: f for f in spec.filters if f.expose_as}
    produced = {*spec.grain, *spec.rollup, *spec.compute, *exposed}
    projection: list[ColumnElement] = []
    for oc in spec.output:
        if oc not in produced:
            raise guards.GuardError(f"output column not produced by the spec: {oc!r}")
        if oc in exposed:
            el = _expose_filter_value(exposed[oc], params or {})
        else:
            el = out_ns[oc] if oc in spec.compute else agg.c[oc]
        projection.append(el.label(oc))

    stmt = select(*projection).select_from(agg)
    if spec.having:
        stmt = stmt.where(compile_expr(spec.having, out_ns))
    if spec.order_by:
        sortable = {*spec.grain, *spec.rollup, *spec.compute}
        order_cols = []
        for name in spec.order_by:
            if name not in sortable:
                raise guards.GuardError(f"order_by column not produced by the spec: {name!r}")
            order_cols.append(out_ns[name] if name in spec.compute else agg.c[name])
        stmt = stmt.order_by(*order_cols)
    return stmt.limit(settings.query_row_limit)


def _expose_filter_value(f, params: dict) -> ColumnElement:  # noqa: ANN001
    """A filter's chosen runtime value, projected as a constant output column."""
    val = params.get(f.name)
    if val is None or (isinstance(val, str) and not val.strip()):
        return literal(None)
    return bindparam(f"{f.name}__expose", value=_filter_value(f.type, val), type_=_filter_type(f.type))
