"""Execute a rule-report spec on the tenant's datamart (read-only).

Parallels runner.run_query but for the declarative rule engine: compile the spec
(+ runtime filter params) to SQL, run the SELECT-only guard, execute inside the
tenant-scoped read-only connection, and return a QueryResult (same shape reports
already use for view/export)."""

from __future__ import annotations

from sqlalchemy.dialects import postgresql

from app.core.logging import get_logger
from app.core.tenancy import TenantContext
from app.db.datamart import datamart_connection
from app.domain.rule_report import RuleReportSpec
from app.query_engine import guards
from app.query_engine.rule_compiler import compile_rule_report
from app.query_engine.runner import QueryResult, _sha256, result_checksum

log = get_logger(__name__)


def run_rule_report(
    *,
    ctx: TenantContext,
    datamart_key: str,
    spec: RuleReportSpec,
    params: dict | None = None,
) -> QueryResult:
    stmt = compile_rule_report(spec, params or {})
    sql_text = str(stmt.compile(dialect=postgresql.dialect()))   # parameterized (audit/guard)
    guards.assert_select_only(sql_text)
    with datamart_connection(ctx, datamart_key) as conn:
        result = conn.execute(stmt)
        columns = list(result.keys())
        rows = [dict(zip(columns, r, strict=False)) for r in result.fetchall()]
    log.info("rule_report_executed", report=spec.name, row_count=len(rows))
    return QueryResult(
        columns=columns, rows=rows, sql=sql_text, row_count=len(rows), truncated=False,
        compiled_sql_hash=_sha256(sql_text),
        result_checksum=result_checksum(columns, rows),
    )
