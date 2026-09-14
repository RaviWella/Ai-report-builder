"""Safe expression compiler for rule-report specs.

Compiles a string expression (a `when` condition, a `value`, a rollup/compute
formula) into a parameterised SQLAlchemy element, by walking a parsed AST with a
STRICT whitelist. Nothing is eval'd; only the operators/functions below are
allowed, and every bare name must resolve in the supplied namespace (a source
column, a constant, or a previously-defined expression) — an unknown name raises.

Allowed:
  literals        numbers, strings
  names           namespace lookup (column / constant / define)
  arithmetic      + - * /  and unary + -
  comparison      == != < <= > >=  and  x in (a, b, ...)
  boolean         and  or  not
  functions       greatest, least, max, min, coalesce, abs, round, time,
                  hours_between
                  (max/min are row-level → greatest/least; time('HH:MM:SS')
                  casts a string literal to a clock-time value so it can be
                  compared against a `time`-typed column — a bare string
                  literal compared to a `time` column fails in Postgres with
                  "operator does not exist: time <= character varying", since
                  an untyped column() has no type for the comparison operator
                  to coerce the literal against; hours_between(start, end) is
                  (end - start) as decimal hours — works for a time/time pair
                  (same-day duration, e.g. a shift start to a punch time) or a
                  timestamp/timestamp pair (e.g. two datetime columns spanning
                  a midnight rollover) via Postgres's native `-` on either,
                  wrapped in `extract(epoch from ...) / 3600`. Combine a plain
                  date column with a time via `+` first — Postgres resolves
                  `date + time -> timestamp` natively — to build the second
                  operand when one side is a bare time and the other already
                  spans possibly-different calendar days)
"""

from __future__ import annotations

import ast

from sqlalchemy import Time, and_, cast, extract, func, literal, not_, or_
from sqlalchemy.sql.elements import ColumnElement

from app.query_engine import guards

_FUNCS = {"greatest", "least", "max", "min", "coalesce", "abs", "round", "time", "hours_between"}


def _as_element(v: object) -> ColumnElement:
    return v if isinstance(v, ColumnElement) else literal(v)


def compile_expr(expr: str, ns: dict[str, object]) -> ColumnElement:
    """Compile a single expression string to a SQLAlchemy element. `ns` maps names
    to ColumnElements (columns) or Python scalars (constants)."""
    if not expr or not expr.strip():
        raise guards.GuardError("empty rule expression")
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as exc:
        raise guards.GuardError(f"invalid rule expression: {expr!r}") from exc
    return _eval(tree.body, ns)


def _eval(node: ast.AST, ns: dict[str, object]) -> ColumnElement:
    if isinstance(node, ast.Constant):
        return literal(node.value)

    if isinstance(node, ast.Name):
        if node.id not in ns:
            raise guards.GuardError(f"unknown name in rule expression: {node.id!r}")
        return _as_element(ns[node.id])

    if isinstance(node, ast.BinOp):
        left, right = _eval(node.left, ns), _eval(node.right, ns)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
        raise guards.GuardError(f"operator not allowed: {type(node.op).__name__}")

    if isinstance(node, ast.UnaryOp):
        if isinstance(node.op, ast.UAdd):
            return _eval(node.operand, ns)
        if isinstance(node.op, ast.USub):
            return -_eval(node.operand, ns)
        if isinstance(node.op, ast.Not):
            return not_(_eval(node.operand, ns))
        raise guards.GuardError(f"unary operator not allowed: {type(node.op).__name__}")

    if isinstance(node, ast.BoolOp):
        parts = [_eval(v, ns) for v in node.values]
        return and_(*parts) if isinstance(node.op, ast.And) else or_(*parts)

    if isinstance(node, ast.Compare):
        if len(node.ops) != 1:
            raise guards.GuardError("chained comparisons are not allowed")
        left = _eval(node.left, ns)
        op = node.ops[0]
        if isinstance(op, ast.In):
            return left.in_([_literal_of(c) for c in _iter_seq(node.comparators[0])])
        if isinstance(op, ast.NotIn):
            return left.notin_([_literal_of(c) for c in _iter_seq(node.comparators[0])])
        right = _eval(node.comparators[0], ns)
        for cls, fn in (
            (ast.Eq, lambda: left == right), (ast.NotEq, lambda: left != right),
            (ast.Lt, lambda: left < right), (ast.LtE, lambda: left <= right),
            (ast.Gt, lambda: left > right), (ast.GtE, lambda: left >= right),
        ):
            if isinstance(op, cls):
                return fn()
        raise guards.GuardError(f"comparison not allowed: {type(op).__name__}")

    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in _FUNCS:
            raise guards.GuardError(
                "only greatest/least/max/min/coalesce/abs/round/time/hours_between are allowed")
        name = node.func.id
        if name == "time":
            if len(node.args) != 1 or not isinstance(node.args[0], ast.Constant) \
                    or not isinstance(node.args[0].value, str):
                raise guards.GuardError("time(...) takes exactly one string literal, e.g. time('14:30:00')")
            return cast(literal(node.args[0].value), Time())
        if name == "hours_between":
            if len(node.args) != 2:
                raise guards.GuardError("hours_between(start, end) takes exactly two arguments")
            start, end = _eval(node.args[0], ns), _eval(node.args[1], ns)
            return extract("epoch", end - start) / 3600.0
        args = [_eval(a, ns) for a in node.args]
        if name in ("max", "greatest"):
            return func.greatest(*args)
        if name in ("min", "least"):
            return func.least(*args)
        return getattr(func, name)(*args)

    raise guards.GuardError(f"illegal element in rule expression: {type(node).__name__}")


def _iter_seq(node: ast.AST):
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return node.elts
    raise guards.GuardError("'in' expects a (a, b, ...) sequence of literals")


def _literal_of(node: ast.AST):
    if isinstance(node, ast.Constant):
        return node.value
    raise guards.GuardError("'in' sequence must contain only literals")
