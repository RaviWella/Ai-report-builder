"""Spec -> safe SQL compiler (README §6.3, Architecture §4.5).

Pipeline:
  data_spec + runtime params
    -> resolve refs via the pinned semantic catalogue
    -> SQLAlchemy Core query build (parameterized)
    -> apply guards (refs, joins, row limit)
    -> execute on the read replica          [runner.py]

This module produces a SQLAlchemy `Select`. It is the ONLY place a query takes
shape, and it NEVER concatenates user/filter values into SQL. Every physical table
is materialised once via a TableRegistry so no phantom/cartesian FROMs appear.
"""

from __future__ import annotations

import ast
import operator
import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy import (
    Select, String, and_, asc, case, cast, desc, func, literal, select, union_all,
)
from sqlalchemy.sql.elements import ColumnElement

from app.core.config import settings
from app.domain.enums import AggFn, FieldRole, FieldType, SortDir
from app.domain.report_spec import CalculatedField, DataSpec, FilterClause
from app.domain.semantic import Entity, MetricDef, SemanticCatalog
from app.query_engine import guards
from app.query_engine.filters import apply_aggregate, build_filter
from app.query_engine.periods import is_period_token, resolve_period_value
from app.query_engine.sql_builder import TableRegistry, collect_columns

# A calculated-field expression may contain ONLY refs, numbers, parentheses,
# whitespace and the four arithmetic operators. Anything else is rejected.
_CALC_TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_.]*|\d+(?:\.\d+)?|[()+\-*/]|\s+")
_REF_TOKEN = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")

# Calculated-field expressions are evaluated by walking a parsed AST with a strict
# node whitelist — never eval()/exec(). Names bind to SQLAlchemy column elements;
# the four arithmetic ops + unary +/- build a SQL expression. Anything else raises.
_AST_BINOPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}
_AST_UNARYOPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def _with_resolved_period(f: FilterClause) -> FilterClause:
    """Resolve a symbolic TIME token (`@period:current_year`, …) to a concrete value
    at compile time — the spec's `current_period()`. Non-period filters pass through
    unchanged. The resolved value is still bound as a parameter by build_filter."""
    if is_period_token(f.value):
        return f.model_copy(update={"value": resolve_period_value(f.value)})
    return f


def _eval_calc_ast(node: ast.AST, namespace: dict[str, ColumnElement]) -> Any:
    if isinstance(node, ast.Expression):
        return _eval_calc_ast(node.body, namespace)
    if isinstance(node, ast.BinOp) and type(node.op) in _AST_BINOPS:
        return _AST_BINOPS[type(node.op)](
            _eval_calc_ast(node.left, namespace), _eval_calc_ast(node.right, namespace)
        )
    if isinstance(node, ast.UnaryOp) and type(node.op) in _AST_UNARYOPS:
        return _AST_UNARYOPS[type(node.op)](_eval_calc_ast(node.operand, namespace))
    if isinstance(node, ast.Name):
        if node.id not in namespace:
            raise guards.GuardError(f"Unknown term in calculated expression: {node.id!r}")
        return namespace[node.id]
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return node.value
    raise guards.GuardError(f"Illegal element in calculated expression: {type(node).__name__}")

# Physical column names that identify a payroll period on a period-grained mart.
# Used to INFER the period grain when an entity doesn't declare `period_grain`,
# so catalogues pinned before that field existed still align correctly.
_PERIOD_YEAR_COLS = ("payroll_year", "pay_year", "year")
_PERIOD_MONTH_COLS = ("payroll_month", "pay_month", "month")


def _period_cols(entity: Entity) -> tuple[str, str] | None:
    """The (year, month) physical columns for a period-grained entity, or None.

    Prefers the explicit `period_grain`; otherwise infers from year/month fields
    exposed on the entity's own base table."""
    if entity.period_grain:
        return (entity.period_grain.year_column, entity.period_grain.month_column)
    base_cols = {
        f.physical.column
        for f in entity.fields
        if (f.physical.schema_name or entity.base_schema) == entity.base_schema
        and f.physical.table == entity.base_table
    }
    year = next((c for c in _PERIOD_YEAR_COLS if c in base_cols), None)
    month = next((c for c in _PERIOD_MONTH_COLS if c in base_cols), None)
    return (year, month) if year and month else None


# COUNT / COUNT DISTINCT apply meaningfully to ANY field (e.g. headcount), so they
# are never restricted; only value-aggregations are governed by allowed_aggregations.
_COUNT_FNS = frozenset({AggFn.COUNT, AggFn.COUNT_DISTINCT})


def _assert_agg_allowed(ref: str, fn: AggFn, catalog: SemanticCatalog) -> None:
    """G1 — governance: a value-aggregation on a field must be in that field's
    declared `allowed_aggregations`, so a dynamic report can't compute a nonsensical
    number (AVG of an NIC, SUM of a rate). Gated by settings; COUNT(*) /
    COUNT DISTINCT are always allowed; metric.* / calc.* are governed elsewhere."""
    if not settings.query_enforce_allowed_aggregations:
        return
    if fn in _COUNT_FNS or ref.startswith(("metric.", "calc.")):
        return
    fld = catalog.field_index().get(ref)
    if fld is None:
        return  # unknown ref is caught by validate_refs
    if fn not in fld.allowed_aggregations:
        allowed = [a.value for a in fld.allowed_aggregations] or ["none"]
        raise guards.GuardError(
            f"“{fld.label}” can’t be aggregated with {fn.value.upper()} — "
            f"allowed: {', '.join(allowed)}."
        )


def _require_period_filter(spec: DataSpec, catalog: SemanticCatalog) -> None:
    """L1 — refuse a report that reads a period-grained mart without filtering on a
    period (year/month) field. Such a report would scan all history; a single
    period filter (on any used period-grained entity) bounds the scan and, via the
    compiler's period-aligned joins, propagates across the other period marts.
    Gated by settings.query_require_period_filter; a report with no period-grained
    entity is never affected."""
    used = {r.split(".", 1)[0] for r in _expand_refs(spec.all_refs(), catalog)}
    used.add(spec.entity)
    ent_by_key = catalog.entity_by_key()

    period_cols: dict[str, set[str]] = {}
    for ek in used:
        ent = ent_by_key.get(ek)
        if ent is None:
            continue
        pc = _period_cols(ent)
        if pc:
            period_cols[ek] = set(pc)
    if not period_cols:
        return  # no period-grained entity in play

    fidx = catalog.field_index()
    for f in spec.filters:  # static value OR runtime param both count as "filtered"
        fld = fidx.get(f.ref)
        ek = f.ref.split(".", 1)[0]
        if fld is not None and ek in period_cols and fld.physical.column in period_cols[ek]:
            return

    raise guards.GuardError(
        "This report reads period data (payroll / attendance / paysheet). "
        "Add a period filter (e.g. Year and/or Month) so it doesn't scan all "
        "history — pick a period, or add it as a runtime filter."
    )


@dataclass
class CompiledQuery:
    statement: Select
    column_order: list[str]  # refs (or calc.<name>) in select order, for rendering


def compile_query(
    spec: DataSpec,
    catalog: SemanticCatalog,
    params: dict[str, Any],
    *,
    preview: bool = False,
    row_limit: int | None = None,
) -> CompiledQuery:
    # 1. Guards that don't need the built statement.
    guards.validate_refs(spec, catalog)
    guards.validate_joins(spec, catalog)
    if settings.query_require_period_filter:
        _require_period_filter(spec, catalog)

    # Root tracks the chosen fields (a report built purely from a standalone
    # entity uses that entity as its base, not the builder's "employee" default).
    field_entities = {r.split(".", 1)[0] for r in _expand_refs(spec.all_refs(), catalog)}
    root_entity = catalog.entity_by_key()[catalog.root_for(field_entities, spec.entity)]

    # 2. Materialise every physical table ONCE.
    registry = _build_registry(spec, catalog, root_entity)

    calc_exprs = _build_calculated(spec.calculated_fields, catalog, registry)

    # Summary / unpivot mode: selected measures become ROWS (generic — works for
    # any wide entity, no report-specific code).
    if spec.unpivot and spec.unpivot.measures:
        return _compile_unpivot(spec, catalog, params, registry, root_entity, preview, row_limit)

    # 3. SELECT list. A metric.<key> field is itself an aggregate, so its presence
    #    (like any aggregation) puts the query in grouped mode.
    select_cols: list[ColumnElement] = []
    column_order: list[str] = []
    has_metric = (
        any(f.ref.startswith("metric.") for f in spec.fields)
        or any(a.ref.startswith("metric.") for a in spec.aggregations)
    )
    grouped = bool(spec.group_by or spec.aggregations or has_metric)

    for fs in spec.fields:
        col = _column_for(fs.ref, catalog, registry, calc_exprs)
        if fs.agg is not None and not fs.ref.startswith("metric."):
            _assert_agg_allowed(fs.ref, fs.agg, catalog)
            col = apply_aggregate(col, fs.agg)
        select_cols.append(col.label(fs.label or _default_label(fs.ref)))
        column_order.append(fs.ref)

    for agg in spec.aggregations:
        _assert_agg_allowed(agg.ref, agg.fn, catalog)
        col = _column_for(agg.ref, catalog, registry, calc_exprs)
        select_cols.append(apply_aggregate(col, agg.fn).label(agg.label or f"{agg.fn.value}_{agg.ref}"))
        column_order.append(f"{agg.fn.value}:{agg.ref}")

    if not select_cols:
        raise guards.GuardError("Report has no selected fields")

    root_tbl = registry.get(root_entity.base_schema, root_entity.base_table)
    stmt = select(*select_cols).select_from(root_tbl)

    # 4. JOINs — only declared joins, only to referenced entities.
    stmt = _apply_joins(stmt, spec, catalog, root_entity, registry)

    # 5. WHERE — all values bound as parameters. Incomplete filters (a value-op
    # left blank in the UI, e.g. `designation = ''`) are SKIPPED rather than
    # applied literally, which would silently match zero rows.
    conditions = [
        build_filter(_column_for(f.ref, catalog, registry, calc_exprs), _with_resolved_period(f), params,
                     _field_type_of(f.ref, catalog))
        for f in spec.filters
        if not _is_incomplete_filter(f, params)
    ]
    if conditions:
        stmt = stmt.where(and_(*conditions))

    # 6. GROUP BY. Explicit group_by wins; otherwise, when grouped (metrics/aggs
    #    present), auto-group by every selected non-aggregated DIMENSION field so
    #    "Department + Total Net Pay (metric)" yields valid SQL.
    if grouped:
        if spec.group_by:
            group_refs = spec.group_by
        else:
            fidx = catalog.field_index()
            group_refs = [
                fs.ref for fs in spec.fields
                if fs.agg is None
                and not fs.ref.startswith(("metric.", "calc."))
                and fidx.get(fs.ref) is not None
                and fidx[fs.ref].role == FieldRole.DIMENSION
            ]
        if group_refs:
            group_cols = [_column_for(ref, catalog, registry, calc_exprs) for ref in group_refs]
            stmt = stmt.group_by(*group_cols)

    # 7. ORDER BY.
    for s in spec.sort:
        col = _column_for(s.ref, catalog, registry, calc_exprs)
        stmt = stmt.order_by(asc(col) if s.dir == SortDir.ASC else desc(col))

    # 8. Row limit guard (always present).
    stmt = stmt.limit(guards.resolve_row_limit(preview=preview, requested=row_limit))

    return CompiledQuery(statement=stmt, column_order=column_order)


def _compile_unpivot(
    spec: DataSpec, catalog: SemanticCatalog, params: dict[str, Any],
    registry: TableRegistry, root_entity: Entity, preview: bool, row_limit: int | None,
) -> CompiledQuery:
    """Build `SELECT '<label>', AGG(col)[, count] FROM … WHERE … ` per measure and
    UNION ALL them — one row per measure. Filters/joins apply to every part."""
    up = spec.unpivot
    root_tbl = registry.get(root_entity.base_schema, root_entity.base_table)
    conditions = [
        build_filter(_column_for(f.ref, catalog, registry, {}), _with_resolved_period(f), params,
                     _field_type_of(f.ref, catalog))
        for f in spec.filters
        if not _is_incomplete_filter(f, params)
    ]
    parts = []
    for i, ref in enumerate(up.measures):
        field = catalog.resolve(ref)
        col = _column_for(ref, catalog, registry, {})
        cnt = (
            func.count().filter(and_(col.isnot(None), col != 0))
            if up.count_header else literal(None)
        )
        sub = select(
            literal(i).label("_ord"),
            literal(field.label).label("_label"),
            apply_aggregate(col, up.agg).label("_value"),
            cnt.label("_cnt"),
        ).select_from(root_tbl)
        sub = _apply_joins(sub, spec, catalog, root_entity, registry)
        if conditions:
            sub = sub.where(and_(*conditions))
        parts.append(sub)

    u = union_all(*parts).subquery("u")
    out = [u.c["_label"].label(up.label_header), u.c["_value"].label(up.value_header)]
    column_order = [up.label_header, up.value_header]
    if up.count_header:
        out.append(u.c["_cnt"].label(up.count_header))
        column_order.append(up.count_header)
    stmt = (
        select(*out)
        .select_from(u)
        .order_by(u.c["_ord"])
        .limit(guards.resolve_row_limit(preview=preview, requested=row_limit))
    )
    return CompiledQuery(statement=stmt, column_order=column_order)


# --------------------------------------------------------------------------- #
# Canonical metrics (metric.<key>) — governed named measures resolved to SQL.
# --------------------------------------------------------------------------- #

def _expand_refs(refs: Any, catalog: SemanticCatalog) -> set[str]:
    return catalog.expand_field_refs(refs)


def _metric_column(
    key: str, catalog: SemanticCatalog, registry: TableRegistry, calc_exprs: dict[str, ColumnElement]
) -> ColumnElement:
    m = catalog.metric_index().get(key)
    if m is None:
        raise guards.GuardError(f"Unknown metric: metric.{key}")
    if m.kind in ("aggregate", "count"):
        if m.kind == "count":
            target = _column_for(m.ref, catalog, registry, calc_exprs) if m.ref else None
            if target is None:
                base = func.count()
            else:
                base = func.count(func.distinct(target)) if m.distinct else func.count(target)
        else:
            if not m.ref or m.agg is None:
                raise guards.GuardError(f"Aggregate metric {m.key!r} needs a ref and an agg")
            base = apply_aggregate(_column_for(m.ref, catalog, registry, calc_exprs), m.agg)
        if m.filters:
            conds = [
                build_filter(_column_for(f.ref, catalog, registry, calc_exprs),
                             FilterClause(ref=f.ref, op=f.op, value=f.value), {},
                             _field_type_of(f.ref, catalog))
                for f in m.filters
            ]
            base = base.filter(and_(*conds))
        return base
    if m.kind == "formula":
        # Arithmetic over OTHER metrics only — so ratios/nets combine aggregates
        # correctly (sum(a) - sum(b), claims/premium). Evaluated via the AST walker.
        namespace: dict[str, ColumnElement] = {}
        py_parts: list[str] = []
        counter = 0
        for tok in _CALC_TOKEN.findall(m.expression or ""):
            t = tok.strip()
            if t == "":
                py_parts.append(tok)
            elif t in "()+-*/":
                py_parts.append(t)
            elif _REF_TOKEN.match(t):
                if not t.startswith("metric."):
                    raise guards.GuardError(f"Formula metric {m.key!r} may reference only other metrics, got {t!r}")
                var = f"_m{counter}"
                counter += 1
                namespace[var] = _metric_column(t.split(".", 1)[1], catalog, registry, calc_exprs)
                py_parts.append(var)
            else:
                py_parts.append(t)  # numeric literal
        try:
            tree = ast.parse("".join(py_parts), mode="eval")
        except SyntaxError as exc:
            raise guards.GuardError(f"Invalid metric formula {m.expression!r}: {exc.msg}") from exc
        return _eval_calc_ast(tree, namespace)
    raise guards.GuardError(f"Unknown metric kind: {m.kind!r}")


def _build_registry(spec: DataSpec, catalog: SemanticCatalog, root_entity: Entity) -> TableRegistry:
    registry = TableRegistry()

    expanded = _expand_refs(spec.all_refs(), catalog)
    # Columns referenced by the spec (metric refs expanded to their underlying ones).
    needed = collect_columns(catalog, expanded)

    # Underlying refs of calculated fields (formula expressions + banding cases).
    for calc in spec.calculated_fields:
        for ref in _calc_refs(calc):
            if ref in catalog.field_index():
                field = catalog.resolve(ref)
                entity = catalog.entity_of_ref(ref)
                schema = field.physical.schema_name or entity.base_schema
                needed.setdefault((schema, field.physical.table), set()).add(field.physical.column)

    # Entity base tables + primary keys for every entity in play.
    used_entity_keys = {r.split(".", 1)[0] for r in expanded}
    used_entity_keys.add(spec.entity)
    ent_by_key = catalog.entity_by_key()
    for ek in used_entity_keys:
        ent = ent_by_key[ek]
        needed.setdefault((ent.base_schema, ent.base_table), set()).add(ent.primary_key)

    # Declared join keys.
    name_to_key = {e.name: e.key for e in catalog.entities}
    for j in catalog.joins:
        for ename, key in ((j.left_entity, j.left_key), (j.right_entity, j.right_key)):
            ent = ent_by_key[name_to_key.get(ename, ename)]
            needed.setdefault((ent.base_schema, ent.base_table), set()).add(key)

    # Period-grain columns for every period-grained entity in play — registered
    # up front so the period-aligned join ON clauses can reference them without
    # rebuilding (and thus duplicating) a table clause into a phantom FROM.
    for ek in used_entity_keys:
        ent = ent_by_key[ek]
        pc = _period_cols(ent)
        if pc:
            needed.setdefault((ent.base_schema, ent.base_table), set()).update(pc)

    for (schema, name), cols in needed.items():
        registry.table_for(schema, name, cols)
    return registry


def _is_incomplete_filter(f, params: dict[str, Any]) -> bool:  # noqa: ANN001
    """A value-based filter the user never filled in — skip it instead of applying
    `col = ''`/`col = None` (which would silently return zero rows). Null-checks and
    bound runtime params are always kept."""
    from app.domain.enums import FilterOp

    if f.op in (FilterOp.IS_NULL, FilterOp.IS_NOT_NULL):
        return False
    if f.param is not None:
        # runtime param: only "incomplete" if the caller passed an empty value
        val = params.get(f.param, None)
    else:
        val = f.value
    return val is None or val == "" or (isinstance(val, (list, tuple)) and len(val) == 0)


def _column_for(
    ref: str, catalog: SemanticCatalog, registry: TableRegistry, calc_exprs: dict[str, ColumnElement]
) -> ColumnElement:
    if ref.startswith("calc."):
        name = ref.split(".", 1)[1]
        if name not in calc_exprs:
            raise guards.GuardError(f"Unknown calculated field: {ref!r}")
        return calc_exprs[name]
    if ref.startswith("metric."):
        return _metric_column(ref.split(".", 1)[1], catalog, registry, calc_exprs)
    field = catalog.resolve(ref)
    entity = catalog.entity_of_ref(ref)
    return registry.col_for(field.physical, entity.base_schema)


def _field_type_of(ref: str, catalog: SemanticCatalog) -> FieldType | None:
    """A filter's field type, when it's a plain catalogue ref (not calc./metric.,
    which build_filter's caller never needs to type-cast for) — lets build_filter
    parse a runtime value to match a date/datetime column regardless of operator."""
    if ref.startswith(("calc.", "metric.")):
        return None
    return catalog.resolve(ref).type


def _apply_joins(
    stmt: Select, spec: DataSpec, catalog: SemanticCatalog, root_entity: Entity, registry: TableRegistry
) -> Select:
    used_entities = {r.split(".", 1)[0] for r in _expand_refs(spec.all_refs(), catalog)}
    # include calc underlying entities (formula + banding)
    for calc in spec.calculated_fields:
        for ref in _calc_refs(calc):
            if ref in catalog.field_index():
                used_entities.add(ref.split(".", 1)[0])
    used_entities.discard(spec.entity)
    if not used_entities:
        return stmt

    name_to_key = {e.name: e.key for e in catalog.entities}
    ent_by_key = catalog.entity_by_key()

    # Period-grain alignment: every period-grained mart joins to the root on the
    # employee key, but two period-grained marts joined on employee alone would
    # cross-multiply across periods (employee × payroll_periods × paysheet_periods
    # × …). So the FIRST period-grained entity in the FROM becomes the anchor, and
    # every later period-grained join ALSO matches on (year, month) against it,
    # collapsing the product back to one row per employee per period.
    period_anchor = root_entity if _period_cols(root_entity) else None

    for join in catalog.joins:
        lk = name_to_key.get(join.left_entity, join.left_entity)
        rk = name_to_key.get(join.right_entity, join.right_entity)
        target_key = rk if lk == spec.entity else lk if rk == spec.entity else None
        if target_key is None or target_key not in used_entities:
            continue
        target_entity = ent_by_key[target_key]
        target_tbl = registry.get(target_entity.base_schema, target_entity.base_table)

        left_ent = ent_by_key[lk]
        right_ent = ent_by_key[rk]
        on_clause = registry.col(left_ent.base_schema, left_ent.base_table, join.left_key) == registry.col(
            right_ent.base_schema, right_ent.base_table, join.right_key
        )

        target_pc = _period_cols(target_entity)
        if target_pc is not None:
            if period_anchor is not None and period_anchor.key != target_entity.key:
                anchor_pc = _period_cols(period_anchor)
                on_clause = and_(
                    on_clause,
                    registry.col(period_anchor.base_schema, period_anchor.base_table, anchor_pc[0])
                    == registry.col(target_entity.base_schema, target_entity.base_table, target_pc[0]),
                    registry.col(period_anchor.base_schema, period_anchor.base_table, anchor_pc[1])
                    == registry.col(target_entity.base_schema, target_entity.base_table, target_pc[1]),
                )
            if period_anchor is None:
                period_anchor = target_entity

        stmt = stmt.join(target_tbl, on_clause, isouter=(join.join_type == "left"))
    return stmt


def _build_calculated(
    calcs: list[CalculatedField], catalog: SemanticCatalog, registry: TableRegistry
) -> dict[str, ColumnElement]:
    exprs: dict[str, ColumnElement] = {}
    for calc in calcs:
        if calc.cases:
            exprs[calc.name] = _build_banding(calc, catalog, registry)
        elif calc.lookup and calc.lookup.map:
            exprs[calc.name] = _build_lookup(calc, catalog, registry)
        else:
            exprs[calc.name] = _parse_calc(calc.expression or "", catalog, registry, exprs)
    return exprs


def _build_lookup(
    calc: CalculatedField, catalog: SemanticCatalog, registry: TableRegistry
) -> ColumnElement:
    """Compile a lookup/mapping field into a safe CASE: CAST(on AS text) = key ->
    label, per entry, ELSE default. Keys and labels are bound literals — no raw SQL."""
    lk = calc.lookup
    if lk.on not in catalog.field_index():
        raise guards.GuardError(f"Lookup field {calc.name!r} references unknown ref: {lk.on!r}")
    field = catalog.resolve(lk.on)
    entity = catalog.entity_of_ref(lk.on)
    col = registry.col_for(field.physical, entity.base_schema)
    key_col = cast(col, String)
    whens = [(key_col == literal(str(k)), literal(v)) for k, v in lk.map.items()]
    if not whens:
        raise guards.GuardError(f"Lookup field {calc.name!r} has an empty map")
    else_ = literal(lk.default) if lk.default is not None else literal(None)
    return case(*whens, else_=else_)


def _build_banding(
    calc: CalculatedField, catalog: SemanticCatalog, registry: TableRegistry
) -> ColumnElement:
    """Compile a banding field into a parameterized SQLAlchemy CASE expression.

    Conditions reuse the whitelisted filter operators (values bound); branch labels
    are bound literals. No raw SQL, no string concatenation."""
    whens = []
    for c in calc.cases:
        if c.ref not in catalog.field_index():
            raise guards.GuardError(f"Banding field {calc.name!r} references unknown ref: {c.ref!r}")
        field = catalog.resolve(c.ref)
        entity = catalog.entity_of_ref(c.ref)
        col = registry.col_for(field.physical, entity.base_schema)
        clause = FilterClause(ref=c.ref, op=c.op, value=c.value)
        whens.append((build_filter(col, clause, {}, field.type), literal(c.label)))
    if not whens:
        raise guards.GuardError(f"Banding field {calc.name!r} has no cases")
    else_ = literal(calc.else_label) if calc.else_label is not None else literal(None)
    return case(*whens, else_=else_)


def _calc_refs(calc: CalculatedField) -> set[str]:
    """All non-calc semantic refs a calculated field depends on (formula + cases)."""
    refs: set[str] = set()
    if calc.expression:
        refs |= {t for t in _refs_in_expression(calc.expression) if not t.startswith("calc.")}
    refs |= {c.ref for c in calc.cases}
    if calc.lookup and calc.lookup.on:
        refs.add(calc.lookup.on)
    return refs


def _refs_in_expression(expression: str) -> set[str]:
    return {t for t in _CALC_TOKEN.findall(expression) if _REF_TOKEN.match(t.strip())}


def _parse_calc(
    expression: str, catalog: SemanticCatalog, registry: TableRegistry, existing: dict
) -> ColumnElement:
    tokens = _CALC_TOKEN.findall(expression)
    if "".join(tokens) != expression:
        raise guards.GuardError(f"Illegal characters in calculated expression: {expression!r}")

    namespace: dict[str, ColumnElement] = {}
    py_parts: list[str] = []
    counter = 0
    for tok in tokens:
        t = tok.strip()
        if t == "":
            py_parts.append(tok)
        elif t in "()+-*/":
            py_parts.append(t)
        elif _REF_TOKEN.match(t):
            if t.startswith("calc."):
                col = existing.get(t.split(".", 1)[1])
                if col is None:
                    raise guards.GuardError(f"Calculated field references unknown calc: {t!r}")
            else:
                if t not in catalog.field_index():
                    raise guards.GuardError(f"Calculated field references unknown ref: {t!r}")
                field = catalog.resolve(t)
                entity = catalog.entity_of_ref(t)
                col = registry.col_for(field.physical, entity.base_schema)
            var = f"_c{counter}"
            counter += 1
            namespace[var] = col
            py_parts.append(var)
        else:  # numeric literal
            py_parts.append(t)

    safe_expr = "".join(py_parts)
    try:
        tree = ast.parse(safe_expr, mode="eval")
    except SyntaxError as exc:
        raise guards.GuardError(f"Invalid calculated expression {expression!r}: {exc.msg}") from exc
    return _eval_calc_ast(tree, namespace)


def _default_label(ref: str) -> str:
    return ref.split(".", 1)[-1].replace("_", " ").title()
