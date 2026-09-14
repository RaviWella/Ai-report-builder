"""Execute a compiled query on the datamart read replica (Architecture §4.5).

This is the only component that issues SQL against the datamart. It compiles the
SQL string for caching/audit, runs the final SELECT-only guard, then executes
read-only inside the tenant-scoped connection.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from sqlalchemy.dialects import postgresql

from app.core.logging import get_logger
from app.core.tenancy import TenantContext
from app.db.datamart import datamart_connection
from app.domain.report_spec import DataSpec
from app.domain.semantic import SemanticCatalog
from app.query_engine import guards
from app.query_engine.compiler import CompiledQuery, compile_query

log = get_logger(__name__)


@dataclass
class QueryResult:
    columns: list[str]
    rows: list[dict[str, Any]]
    sql: str
    row_count: int
    truncated: bool
    # WS-1 provenance. compiled_sql_hash + result_checksum are query-level and
    # deterministic; the rest are stamped by the report run-logger.
    compiled_sql_hash: str = ""
    result_checksum: str = ""
    run_id: str | None = None
    semantic_version_ref: int | None = None
    datamart_snapshot_ref: str | None = None
    # True when this result was served from the Redis result cache (no datamart hit).
    from_cache: bool = False


_UNIT, _RECORD = "\x1f", "\x1e"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def result_checksum(columns: list[str], rows: list[dict[str, Any]]) -> str:
    """A deterministic, ORDER-INDEPENDENT hash of a result set: hash each row's
    values (in column order), sort the row hashes, then hash that with the column
    list. Same data → same checksum regardless of row order; any value/column/row
    change moves it."""
    row_hashes = sorted(
        _sha256(_UNIT.join("" if r.get(c) is None else str(r.get(c)) for c in columns))
        for r in rows
    )
    return _sha256(_UNIT.join(columns) + _RECORD + "\n".join(row_hashes))


def _assert_within_cost_budget(conn, statement) -> None:  # noqa: ANN001
    """L6 — cost governor. When enabled, EXPLAIN the statement (planner only — the
    query is NOT executed) and refuse it if the planner's total cost exceeds the
    configured limit, so one runaway report can't saturate the shared datamart for
    the other tenants. OFF by default; an EXPLAIN failure never blocks a run."""
    from app.core.config import settings
    from app.query_engine.explain import explain_plan

    if not settings.query_cost_guard_enabled:
        return
    limit = settings.query_max_estimated_cost
    if not limit or limit <= 0:
        return
    try:
        cost = explain_plan(conn, statement).get("total_cost")
    except Exception as exc:  # noqa: BLE001 - never block a run because EXPLAIN failed
        log.warning("cost_guard_explain_failed", error=str(exc)[:160])
        return
    if cost is not None and cost > limit:
        log.info("cost_guard_rejected", estimated_cost=cost, limit=limit)
        raise guards.GuardError(
            "This report is too large to run as-is — add a period filter or narrow it "
            f"(estimated cost {int(cost):,} exceeds the limit {int(limit):,})."
        )


def render_sql(compiled: CompiledQuery) -> str:
    """Render the compiled statement as parameterized PostgreSQL (for cache/audit).

    literal_binds is intentionally OFF — parameters stay as bind placeholders, so
    cached SQL never embeds values."""
    return str(
        compiled.statement.compile(
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": False}
        )
    )


def run_query(
    *,
    ctx: TenantContext,
    datamart_key: str,
    spec: DataSpec,
    catalog: SemanticCatalog,
    params: dict[str, Any],
    preview: bool = False,
    row_limit: int | None = None,
    snapshot_ref: str | None = None,
    use_cache: bool = False,
) -> QueryResult:
    compiled = compile_query(spec, catalog, params, preview=preview, row_limit=row_limit)
    sql_text = render_sql(compiled)
    guards.assert_select_only(sql_text)
    sql_hash = _sha256(sql_text)
    # Cache key must reflect the ACTUAL bound values — filter literals baked into the
    # spec (e.g. status='active' vs status='resigned') render identically as
    # placeholders, so a parameterized hash would collide and serve the wrong cached
    # result. Hash the literal-bound SQL for the key only; execution stays parameterized.
    cache_hash = _sha256(
        str(compiled.statement.compile(
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
        ))
    )
    cap = guards.resolve_row_limit(preview=preview, requested=row_limit)

    def _execute() -> QueryResult:
        with datamart_connection(ctx, datamart_key) as conn:
            if not preview:
                _assert_within_cost_budget(conn, compiled.statement)
            result = conn.execute(compiled.statement)
            columns = list(result.keys())
            rows = [dict(zip(columns, r, strict=False)) for r in result.fetchall()]
        truncated = len(rows) >= cap
        log.info(
            "report_query_executed", row_count=len(rows), preview=preview, truncated=truncated,
        )
        return QueryResult(
            columns=columns, rows=rows, sql=sql_text, row_count=len(rows), truncated=truncated,
            compiled_sql_hash=sql_hash, result_checksum=result_checksum(columns, rows),
        )

    # Cache only with a freshness anchor (snapshot_ref): the key embeds it, so a
    # warehouse refresh makes old entries unreachable and stale data is never served.
    if not (use_cache and snapshot_ref):
        return _execute()
    return _run_cached(ctx, cache_hash, params, snapshot_ref, _execute)


def _run_cached(ctx, sql_hash, params, snapshot_ref, execute):  # noqa: ANN001
    """Single-flight result cache around `execute`. Any cache failure degrades to a
    direct execute — the cache is never allowed to break (or block) a run."""
    from app.services.result_cache import cache, make_key

    rc = cache()
    if not rc.enabled:
        return execute()
    key = make_key(ctx.tenant_id, sql_hash, params, snapshot_ref)

    hit = rc.get(key)
    if hit is not None:
        hit.from_cache = True
        log.info("report_query_cache_hit", rows=hit.row_count)
        return hit

    owns = rc.acquire(key)
    if not owns:  # another caller is computing — wait briefly for their result
        waited = rc.wait_for(key)
        if waited is not None:
            waited.from_cache = True
            log.info("report_query_cache_hit_waited", rows=waited.row_count)
            return waited
    try:
        result = execute()
        rc.set(key, result)
        return result
    finally:
        if owns:
            rc.release(key)
