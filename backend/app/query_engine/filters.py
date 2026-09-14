"""Filter + aggregation translation (FR-B2, FR-B3).

Every operator is a whitelisted mapping to a SQLAlchemy expression. Values are
ALWAYS bound parameters — there is no path from a filter value to a string-
concatenated SQL fragment (security §7.2). Runtime filter values arrive via the
`params` dict keyed by RuntimeParam.name.
"""

from __future__ import annotations

import datetime
from typing import Any

from sqlalchemy import and_, func
from sqlalchemy.sql.elements import ColumnClause, ColumnElement

from app.domain.enums import AggFn, FieldType, FilterOp
from app.domain.report_spec import FilterClause
from app.query_engine.guards import GuardError

# A runtime filter value always arrives as plain JSON, and a BUILDER-FIXED
# (static) value is always typed as a plain string in the builder's own text
# field regardless of the field's real type — with no type on the
# dynamically-introspected column (sql_builder.TableRegistry builds plain
# untyped Column(name) objects), a raw string bind falls back to a generic/
# varchar type. Postgres has no date/boolean/integer-vs-varchar comparison
# operator, so e.g. `work_date >= '2026-01-01'` or `is_public_holiday =
# 'true'` fails with "operator does not exist: ... character varying".
# Parsing the value into a real Python object matching the field's own
# semantic type fixes this for every operator — SQLAlchemy infers the
# correct bind type from the Python value itself, no column type or SQL-
# level CAST needed. (A runtime NUMBER filter's own control already sends a
# real JS number, not a string — this is a no-op for that case; it only
# matters for a static numeric value, or any boolean value, string or not.)
_TRUE_STRINGS = {"true", "1", "yes"}
_FALSE_STRINGS = {"false", "0", "no"}


def _typed(value: Any, field_type: FieldType | None) -> Any:
    if field_type == FieldType.BOOLEAN and isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in _TRUE_STRINGS:
            return True
        if lowered in _FALSE_STRINGS:
            return False
        return value  # not a recognized boolean string — leave it, fail loudly rather than guess
    if not isinstance(value, str):
        return value
    if field_type == FieldType.DATE:
        return datetime.date.fromisoformat(value)
    if field_type == FieldType.DATETIME:
        return datetime.datetime.fromisoformat(value)
    if field_type == FieldType.INTEGER:
        return int(value)
    if field_type == FieldType.DECIMAL:
        return float(value)
    return value


def build_filter(
    col: ColumnClause, clause: FilterClause, params: dict[str, Any],
    field_type: FieldType | None = None,
) -> ColumnElement:
    """Return a SQLAlchemy boolean expression for one filter clause.

    The actual value is resolved from `clause.value` (builder-fixed) or from
    `params[clause.param]` (runtime). SQLAlchemy binds it as a parameter.
    `field_type` (when known) parses a string value to match a date/datetime/
    boolean/integer/decimal column.
    """
    op = clause.op

    if op in (FilterOp.IS_NULL, FilterOp.IS_NOT_NULL):
        return col.is_(None) if op == FilterOp.IS_NULL else col.isnot(None)

    value = _resolve_value(clause, params)

    if op == FilterOp.EQ:
        return col == _typed(value, field_type)
    if op == FilterOp.NEQ:
        return col != _typed(value, field_type)
    if op == FilterOp.GT:
        return col > _typed(value, field_type)
    if op == FilterOp.LT:
        return col < _typed(value, field_type)
    if op == FilterOp.GTE:
        return col >= _typed(value, field_type)
    if op == FilterOp.LTE:
        return col <= _typed(value, field_type)
    if op == FilterOp.CONTAINS:
        # bound param; ilike pattern assembled by SQLAlchemy, value still bound
        return col.ilike(func.concat("%", value, "%"))
    if op == FilterOp.IN:
        if not isinstance(value, (list, tuple)):
            raise GuardError(f"Operator 'in' on {clause.ref!r} requires a list value")
        return col.in_([_typed(v, field_type) for v in value])
    if op == FilterOp.BETWEEN:
        if not (isinstance(value, (list, tuple)) and len(value) == 2):
            raise GuardError(f"Operator 'between' on {clause.ref!r} requires [lo, hi]")
        return and_(col >= _typed(value[0], field_type), col <= _typed(value[1], field_type))

    raise GuardError(f"Unsupported filter operator: {op!r}")


def _resolve_value(clause: FilterClause, params: dict[str, Any]) -> Any:
    if clause.param is not None:
        if clause.param not in params:
            raise GuardError(f"Missing runtime parameter {clause.param!r} for filter on {clause.ref!r}")
        return params[clause.param]
    return clause.value


_AGG_FUNCS = {
    AggFn.SUM: func.sum,
    AggFn.AVG: func.avg,
    AggFn.COUNT: func.count,
    AggFn.MIN: func.min,
    AggFn.MAX: func.max,
}


def apply_aggregate(col: ColumnClause, fn: AggFn) -> ColumnElement:
    if fn == AggFn.COUNT_DISTINCT:
        return func.count(col.distinct())
    if fn not in _AGG_FUNCS:
        raise GuardError(f"Unsupported aggregation: {fn!r}")
    return _AGG_FUNCS[fn](col)
