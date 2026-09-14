"""Canonical metrics layer — governed named measures on top of the field catalogue.

A metric is the single definition for a business number (Headcount, Total Net Pay,
Loss Ratio), so it means the same thing in every report. Defining one VALIDATES
that it compiles against the live catalogue (bad ref / bad formula is rejected up
front), then stores it per tenant; the query engine resolves `metric.<key>` to SQL.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.tenancy import TenantContext
from app.db.metadata import SemanticMetric
from app.domain.enums import AggFn, AuditAction
from app.domain.report_spec import DataSpec, FieldSelection
from app.domain.semantic import MetricDef, SemanticCatalog
from app.query_engine import guards
from app.query_engine.compiler import compile_query
from app.services.audit_service import AuditService
from app.services.semantic_service import SemanticService


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def assert_recertification_ok(prior: MetricDef | None, new: MetricDef) -> None:
    """Governance: a certified metric is the approved single definition, so it can't
    be silently overwritten by an uncertified edit — re-defining one must itself be
    certified (a deliberate re-certification). Pure, so it's unit-tested directly."""
    if prior is not None and prior.certified and not new.certified:
        raise guards.GuardError(
            f"Metric {new.key!r} is certified — re-defining it requires "
            "re-certification (submit it as certified, with an owner)."
        )


def load_active_metrics(db: Session, tenant_id: str) -> list[MetricDef]:
    """The tenant's current metric set (standalone so SemanticService can load it
    into a catalogue without importing the metrics service)."""
    rows = db.execute(
        select(SemanticMetric).where(
            SemanticMetric.active.is_(True)
        )
    ).scalars().all()
    return [MetricDef.model_validate(r.definition) for r in rows]


# Default metrics proposed on seeding — only those whose refs exist are kept.
_SEED_CANDIDATES = [
    MetricDef(key="headcount", label="Headcount", unit="count", kind="count",
              ref="employee.emp_no", distinct=True, source="seed",
              aliases=["headcount", "number of employees", "employee count"]),
    MetricDef(key="total_gross", label="Total Gross", unit="currency", kind="aggregate",
              agg=AggFn.SUM, ref="paysheet.gross_salary", source="seed", aliases=["total gross"]),
    MetricDef(key="total_net", label="Total Net Pay", unit="currency", kind="aggregate",
              agg=AggFn.SUM, ref="paysheet.net_salary", source="seed", aliases=["total net", "total net pay"]),
    MetricDef(key="total_deductions", label="Total Deductions", unit="currency", kind="aggregate",
              agg=AggFn.SUM, ref="paysheet.total_deduction", source="seed", aliases=["total deductions"]),
]


class MetricsService:
    def __init__(self, db: Session):
        self.db = db
        self.semantic = SemanticService(db)
        self.audit = AuditService(db)

    def list(self, ctx: TenantContext) -> list[MetricDef]:
        return load_active_metrics(self.db, ctx.tenant_id)

    def define(self, ctx: TenantContext, metric: MetricDef) -> MetricDef:
        """Validate the metric compiles against the live catalogue, then store it
        (superseding any prior definition of the same key). Raises GuardError /
        ValueError for an invalid definition."""
        if not metric.key.replace("_", "").isalnum():
            raise ValueError("Metric key must be alphanumeric / underscores only.")
        catalog = self._catalog_with(ctx, metric)
        self._assert_compiles(catalog, metric.key)

        existing = list(self.db.execute(
            select(SemanticMetric).where(
                SemanticMetric.key == metric.key, SemanticMetric.active.is_(True),
            )
        ).scalars())

        # Governance: a certified metric can't be silently overwritten (see fn).
        prior = MetricDef.model_validate(existing[0].definition) if existing else None
        assert_recertification_ok(prior, metric)

        # Stamp certification provenance when the metric is certified.
        if metric.certified:
            metric.certified_by = metric.certified_by or ctx.acting_user_id
            metric.certified_at = metric.certified_at or _now_iso()

        for row in existing:
            row.active = False
        self.db.add(SemanticMetric(
            key=metric.key,
            definition=metric.model_dump(mode="json"), created_by=ctx.acting_user_id,
        ))
        self.db.commit()
        self.audit.log(
            user_id=ctx.acting_user_id, action=AuditAction.AI_INTERACTION,
            detail={"mode": "metric_define", "key": metric.key, "kind": metric.kind},
        )
        return metric

    def seed_defaults(self, ctx: TenantContext) -> list[MetricDef]:
        """Create the default metrics whose underlying refs exist in this tenant's
        catalogue and aren't already defined. Best-effort, idempotent."""
        catalog = self.semantic.get_active_catalog(ctx.tenant_id)
        known_refs = set(catalog.field_index().keys())
        existing = {m.key for m in self.list(ctx)}
        created: list[MetricDef] = []
        for cand in _SEED_CANDIDATES:
            if cand.key in existing:
                continue
            if cand.ref and cand.ref not in known_refs:
                continue
            try:
                created.append(self.define(ctx, cand))
            except (guards.GuardError, ValueError):
                continue
        return created

    def _catalog_with(self, ctx: TenantContext, metric: MetricDef) -> SemanticCatalog:
        catalog = self.semantic.get_active_catalog(ctx.tenant_id)
        catalog = catalog.model_copy(deep=True)
        catalog.metrics = [m for m in self.list(ctx) if m.key != metric.key] + [metric]
        return catalog

    def _assert_compiles(self, catalog: SemanticCatalog, key: str) -> None:
        underlying = catalog.expand_field_refs([f"metric.{key}"])
        if not underlying:
            raise guards.GuardError(f"Metric {key!r} references no real fields")
        entity = next(iter(sorted(underlying))).split(".", 1)[0]
        spec = DataSpec(entity=entity, fields=[FieldSelection(ref=f"metric.{key}")])
        compile_query(spec, catalog, {})  # raises GuardError on a bad ref / formula
