"""L0 — slow-query observability.

Aggregates the run-lineage log (`report_runs`) into per-query-shape latency stats,
so the hot+slow set is visible BEFORE we optimise. This is the data that targets
every other performance layer: which shapes deserve a rollup (L3), which columns
deserve an index (L4), and what to set the cost-guard threshold to (L6).

Reads the metadata DB only (never the datamart) — it's all already-recorded
provenance, so it's cheap and safe to expose to builders/admins.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.metadata import ReportRun


def slow_queries(db: Session, *, limit: int = 20) -> list[dict[str, Any]]:
    """Per (compiled_sql_hash, report) latency profile for the current tenant schema,
    worst p95 first. Session must already be tenant-scoped via search_path."""
    p95 = func.percentile_cont(0.95).within_group(ReportRun.duration_ms)
    stmt = (
        select(
            ReportRun.compiled_sql_hash.label("sql_hash"),
            ReportRun.report_id.label("report_id"),
            func.count().label("runs"),
            func.round(func.avg(ReportRun.duration_ms)).label("avg_ms"),
            func.max(ReportRun.duration_ms).label("max_ms"),
            p95.label("p95_ms"),
            func.round(func.avg(ReportRun.row_count)).label("avg_rows"),
            func.max(ReportRun.executed_at).label("last_run"),
        )
        .where(ReportRun.duration_ms.isnot(None))
        .group_by(ReportRun.compiled_sql_hash, ReportRun.report_id)
        .order_by(func.coalesce(p95, 0).desc())
        .limit(limit)
    )
    out: list[dict[str, Any]] = []
    for r in db.execute(stmt).all():
        m = r._mapping
        out.append(
            {
                "sql_hash": m["sql_hash"],
                "report_id": m["report_id"],
                "runs": int(m["runs"] or 0),
                "avg_ms": int(m["avg_ms"]) if m["avg_ms"] is not None else None,
                "p95_ms": int(m["p95_ms"]) if m["p95_ms"] is not None else None,
                "max_ms": int(m["max_ms"]) if m["max_ms"] is not None else None,
                "avg_rows": int(m["avg_rows"]) if m["avg_rows"] is not None else None,
                "last_run": m["last_run"].isoformat() if m["last_run"] is not None else None,
            }
        )
    return out
