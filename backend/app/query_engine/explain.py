"""EXPLAIN support — query plan / cost without executing the query.

Two consumers:
  - the SQL-preview endpoint (show a DBA the compiled SQL + planner estimate), and
  - the cost governor (reject a runaway query before it runs — L6).

`Explain` wraps any SELECT in `EXPLAIN (FORMAT JSON) …`. With `analyze=False`
(the default) PostgreSQL only PLANS the statement — it never executes it — so this
is safe on the read-only datamart and cheap. Parameters stay bound through
SQLAlchemy (no string concatenation, no injection surface).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.expression import ClauseElement, Executable


class Explain(Executable, ClauseElement):
    """`EXPLAIN (FORMAT <fmt>[, ANALYZE]) <statement>` as a SQLAlchemy construct.

    analyze defaults to False — the query is planned, NOT run. Only flip it on a
    primary/sandbox you are willing to actually execute against; never on the
    shared read replica for an untrusted/heavy spec.
    """

    inherit_cache = False

    def __init__(self, statement: Any, *, analyze: bool = False, fmt: str = "json") -> None:
        self.statement = statement
        self.analyze = analyze
        self.fmt = fmt


@compiles(Explain, "postgresql")
def _pg_explain(element: Explain, compiler: Any, **kw: Any) -> str:  # noqa: ANN401
    opts = [f"FORMAT {element.fmt.upper()}"]
    if element.analyze:
        opts.append("ANALYZE")
    return f"EXPLAIN ({', '.join(opts)}) " + compiler.process(element.statement, **kw)


def top_plan(plan_json: Any) -> dict[str, Any]:
    """The root plan node from an `EXPLAIN (FORMAT JSON)` payload.

    psycopg returns the JSON already parsed as `[{"Plan": {...}, ...}]`. Tolerates
    the raw-string form too. Returns {} if the shape is unexpected (callers treat a
    missing estimate as 'unknown', never as 0)."""
    import json

    if isinstance(plan_json, str):
        try:
            plan_json = json.loads(plan_json)
        except ValueError:
            return {}
    if isinstance(plan_json, list) and plan_json and isinstance(plan_json[0], dict):
        node = plan_json[0].get("Plan")
        return node if isinstance(node, dict) else {}
    return {}


def estimated_cost(plan_json: Any) -> float | None:
    """Planner's total cost estimate (arbitrary cost units), or None if unknown."""
    node = top_plan(plan_json)
    cost = node.get("Total Cost")
    return float(cost) if isinstance(cost, (int, float)) else None


def estimated_rows(plan_json: Any) -> int | None:
    """Planner's estimated output row count, or None if unknown."""
    node = top_plan(plan_json)
    rows = node.get("Plan Rows")
    return int(rows) if isinstance(rows, (int, float)) else None


def explain_plan(conn: Any, statement: Any) -> dict[str, Any]:  # noqa: ANN401
    """Run `EXPLAIN (FORMAT JSON)` for `statement` on `conn` (no ANALYZE → the
    query is NOT executed) and return {total_cost, est_rows, plan}."""
    plan_json = conn.execute(Explain(statement)).scalar()
    return {
        "total_cost": estimated_cost(plan_json),
        "est_rows": estimated_rows(plan_json),
        "plan": plan_json,
    }
