"""Semantic layer admin router (SRS §9: support/admin & tech team).

Exposes the metadata-only catalogue to the builder UI, plus introspection and
version save for the tech team. Physical names are present in the full catalogue
(builder needs entity structure) but the AI projection is metadata-only.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import db_session
from app.core.logging import get_logger
from app.core.security import AdminRoles, BuilderRoles, require_roles
from app.core.tenancy import TenantContext, get_tenant_context
from app.domain.semantic import GlossaryTerm, MetricDef, SemanticCatalog
from app.services.semantic_service import SemanticService
from app.services.tenant_scope import resolve_datamart_key

log = get_logger(__name__)

router = APIRouter(prefix="/semantic", tags=["semantic"])


@router.get("/catalog")
def get_catalog(
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    """Active catalogue for the builder (entities/dimensions/measures/joins)."""
    catalog = SemanticService(db).get_active_catalog(ctx.tenant_id)
    return catalog.model_dump(mode="json")


@router.get("/fields")
def list_fields(
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> list[dict]:
    """Metadata-only field list (the exact shape the AI sees), incl. metrics."""
    return SemanticService(db).get_active_catalog(ctx.tenant_id).metadata_for_ai()


@router.get("/fields/builder")
def list_fields_for_builder(
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> list[dict]:
    """Field list for the HUMAN field picker — same as /fields plus sample
    values and an anchor-entity flag, to disambiguate a label that repeats
    across entities (e.g. "Designation" on both Employee and a historical
    mart). Never sent to the AI — see metadata_for_builder()'s docstring."""
    return SemanticService(db).get_active_catalog(ctx.tenant_id).metadata_for_builder()


@router.get("/metrics")
def list_metrics(
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> list[dict]:
    """Canonical metrics for this tenant."""
    from app.services.metrics_service import MetricsService

    return [m.model_dump(mode="json") for m in MetricsService(db).list(ctx)]


@router.post("/metrics", dependencies=[Depends(require_roles(*BuilderRoles))])
def define_metric(
    metric: MetricDef,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    """Define (or supersede) a canonical metric. Rejected if it doesn't compile."""
    from fastapi import HTTPException

    from app.query_engine.guards import GuardError
    from app.services.metrics_service import MetricsService

    try:
        saved = MetricsService(db).define(ctx, metric)
    except (GuardError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid metric: {exc}") from exc
    return saved.model_dump(mode="json")


@router.post("/metrics/seed-defaults", dependencies=[Depends(require_roles(*BuilderRoles))])
def seed_default_metrics(
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    """Create the default metrics whose underlying fields exist for this tenant."""
    from app.services.metrics_service import MetricsService

    created = MetricsService(db).seed_defaults(ctx)
    return {"created": [m.key for m in created]}


@router.get("/glossary")
def list_glossary(
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> list[dict]:
    """The tenant's business glossary (term -> definition -> ref)."""
    from app.services.glossary_service import GlossaryService

    return [t.model_dump(mode="json") for t in GlossaryService(db).list(ctx)]


@router.post("/glossary", dependencies=[Depends(require_roles(*BuilderRoles))])
def define_glossary_term(
    term: GlossaryTerm,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    """Define (or supersede) a glossary term. Rejected if its `ref` doesn't resolve."""
    from fastapi import HTTPException

    from app.services.glossary_service import GlossaryService

    try:
        saved = GlossaryService(db).define(ctx, term)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid term: {exc}") from exc
    return saved.model_dump(mode="json")


@router.post("/glossary/seed-defaults", dependencies=[Depends(require_roles(*BuilderRoles))])
def seed_default_glossary(
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    """Create the default business terms whose `ref` resolves for this tenant."""
    from app.services.glossary_service import GlossaryService

    created = GlossaryService(db).seed_defaults(ctx)
    return {"created": [t.term for t in created]}


@router.post("/introspect", dependencies=[Depends(require_roles(*AdminRoles))])
def introspect(
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    """Propose a catalogue from the live datamart (requires replica/VPN). Returns a
    DRAFT catalogue for tech-team review — not saved automatically."""
    
    from app.services.tenant_scope import resolve_datamart_key
    datamart_key = resolve_datamart_key(ctx.tenant_id)
    proposed = SemanticService(db).introspect_datamart(ctx, datamart_key)
    return proposed.model_dump(mode="json")


@router.post("/rebuild", dependencies=[Depends(require_roles(*BuilderRoles))])
def rebuild(
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    """Rebuild the semantic layer: curated core + auto-introspected dynamic
    paysheet pay items (additions/deductions) for this tenant. Saves a NEW
    semantic version (old reports stay pinned). Requires datamart access (VPN)."""
    try:
        datamart_key = resolve_datamart_key(ctx.tenant_id)
        catalog = SemanticService(db).rebuild_catalog(ctx, datamart_key)
        db.commit()
    except Exception as exc:  # surface the real cause instead of a bare 500
        db.rollback()
        log.error("semantic_rebuild_failed", error=str(exc))
        raise HTTPException(
            status_code=502, detail=f"Rebuild failed: {type(exc).__name__}: {exc}"
        ) from exc
    return {
        "version": catalog.version,
        "entities": [e.name for e in catalog.entities],
        "total_fields": sum(len(e.fields) for e in catalog.entities),
    }


@router.post("/catalog", dependencies=[Depends(require_roles(*AdminRoles))])
def save_catalog(
    catalog: SemanticCatalog,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    """Save an enriched catalogue as a new immutable semantic version."""
    catalog.tenant_id = ctx.tenant_id
    svc = SemanticService(db)
    next_version = (svc.repo.latest_version(ctx.tenant_id) or 0) + 1
    catalog.version = next_version
    svc.save_catalog(catalog)
    db.commit()
    return {"saved_version": next_version}
