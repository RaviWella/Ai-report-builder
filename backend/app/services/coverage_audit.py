"""WS-3+ — semantic-layer DATA-CAPTURE coverage audit.

The semantic layer is only as trustworthy as the marts beneath it: a field can be
mapped perfectly yet be empty in the data (e.g. `employee.department` →
`designation_department`, which was 0/325 populated). A correct mapping over an
empty column produces a confident, wrong-looking report — the exact thing that
erodes trust.

This audit is CATALOGUE-DRIVEN: it walks every field the catalogue exposes and
measures, in one query per physical table, how populated each backing column is.
Nothing is hand-listed, so it stays correct as the catalogue or the marts evolve.
It reports three states per field:

  - ok       — the column is populated (coverage > 0)
  - empty    — the column exists but is 0% populated (a data-capture gap)
  - missing  — the catalogue references a column the mart no longer has (drift)

`empty`/`missing` findings are persisted as `completeness` validation results so
they surface alongside the other data-quality checks. The audit never mutates data.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.core.tenancy import TenantContext
from app.db.datamart import datamart_connection
from app.db.metadata import MartValidationResult
from app.query_engine import guards
from app.services.semantic_service import SemanticService

log = get_logger(__name__)


@dataclass
class FieldCoverage:
    ref: str
    label: str
    entity: str
    table: str
    column: str
    total: int | None
    populated: int | None
    coverage: float | None      # populated / total, 0..1
    status: str                 # ok | empty | missing | error


class CoverageAuditService:
    def __init__(self, db: Session):
        self.db = db
        self.semantic = SemanticService(db)

    def run(self, ctx: TenantContext, datamart_key: str, *, persist: bool = True) -> dict:
        catalog = self.semantic.get_active_catalog(ctx.tenant_id)

        # Group every mapped field by its physical (schema, table).
        groups: dict[tuple[str, str], list[tuple[str, str, str, str]]] = {}
        for ent in catalog.entities:
            for f in ent.fields:
                schema = f.physical.schema_name or ent.base_schema
                table = f.physical.table or ent.base_table
                col = f.physical.column
                if schema and table and col:
                    groups.setdefault((schema, table), []).append((f.ref, col, f.label, ent.key))

        results: list[FieldCoverage] = []
        with datamart_connection(ctx, datamart_key) as conn:
            for (schema, table), items in groups.items():
                results.extend(self._audit_table(conn, schema, table, items))

        if persist:
            self._persist(ctx, results)
        results.sort(key=lambda r: (r.status == "ok", r.coverage if r.coverage is not None else 1.0))
        return {"results": [r.__dict__ for r in results], "summary": _summary(results)}

    def _audit_table(
        self, conn, schema: str, table: str, items: list[tuple[str, str, str, str]]
    ) -> list[FieldCoverage]:
        out: list[FieldCoverage] = []
        try:
            present = {
                r[0]
                for r in conn.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_schema = :s AND table_name = :t"
                    ),
                    {"s": schema, "t": table},
                ).all()
            }
        except Exception:  # noqa: BLE001 - table unreachable; report as error
            return [
                FieldCoverage(ref, label, ent, table, col, None, None, None, "error")
                for (ref, col, label, ent) in items
            ]

        existing = [(ref, col, label, ent) for (ref, col, label, ent) in items if col in present]
        for ref, col, label, ent in items:
            if col not in present:
                out.append(FieldCoverage(ref, label, ent, table, col, None, None, None, "missing"))
        if not existing:
            return out

        # One pass over the table: total rows + populated (non-null, non-blank) per
        # column. CAST→text→trim makes "populated" uniform across column types.
        selects = ["count(*) AS _total"] + [
            f'count(NULLIF(btrim(CAST("{col}" AS text)), \'\')) AS c{i}'
            for i, (_ref, col, _l, _e) in enumerate(existing)
        ]
        sql = f'SELECT {", ".join(selects)} FROM "{schema}"."{table}"'
        try:
            guards.assert_select_only(sql)
            row = conn.execute(text(sql)).mappings().first() or {}
        except Exception:  # noqa: BLE001
            return out + [
                FieldCoverage(ref, label, ent, table, col, None, None, None, "error")
                for (ref, col, label, ent) in existing
            ]

        total = int(row.get("_total") or 0)
        for i, (ref, col, label, ent) in enumerate(existing):
            pop = int(row.get(f"c{i}") or 0)
            cov = (pop / total) if total else 0.0
            status = "empty" if (total > 0 and pop == 0) else "ok"
            out.append(FieldCoverage(ref, label, ent, table, col, total, pop, round(cov, 4), status))
        return out

    def _persist(self, ctx: TenantContext, results: list[FieldCoverage]) -> None:
        """Record data-capture gaps (empty/missing fields) as completeness results."""
        run_id = uuid.uuid4().hex
        flagged = [r for r in results if r.status in ("empty", "missing")]
        for r in flagged:
            self.db.add(MartValidationResult(
                validation_run_id=run_id,
                name=f"coverage:{r.ref}", category="completeness", severity="warning",
                status="fail",
                row_count=r.populated,
                description=(
                    f"{r.label} ({r.ref}) is {r.status}: backing column "
                    f"{r.table}.{r.column} "
                    + ("does not exist in the mart" if r.status == "missing"
                       else f"is 0% populated ({r.total} rows)")
                ),
                details={"ref": r.ref, "table": r.table, "column": r.column,
                         "coverage": r.coverage, "status": r.status},
            ))
        self.db.commit()
        log.info("coverage_audit_completed", fields=len(results), flagged=len(flagged))


def _summary(results: list[FieldCoverage]) -> dict:
    return {
        "fields": len(results),
        "ok": sum(1 for r in results if r.status == "ok"),
        "empty": sum(1 for r in results if r.status == "empty"),
        "missing": sum(1 for r in results if r.status == "missing"),
        "errored": sum(1 for r in results if r.status == "error"),
        # Fields a report could select but that carry no data — the trust risk.
        "data_capture_gaps": [r.ref for r in results if r.status in ("empty", "missing")],
    }
