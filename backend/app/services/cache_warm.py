"""Result-cache warming."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.core.tenancy import TenantContext
from app.db.metadata import ReportTemplate
from app.db.pg_tenant_session import worker_pg_session
from app.db.postgres import get_postgres_database
from app.domain.enums import Role
from app.query_engine.runner import run_query
from app.repositories.tenant_provision import list_active_tenants
from app.services.report_service import ReportService
from app.services.result_cache import cache, cached_snapshot_ref
from app.tenancy.pg_schema import subdomain_to_pg_schema
from sqlalchemy import text

log = get_logger(__name__)


def _system_ctx(tenant_id: str) -> TenantContext:
    return TenantContext(
        tenant_id=tenant_id,
        pg_schema=subdomain_to_pg_schema(tenant_id),
        acting_user_id="system",
        role=Role.SYSTEM,
        on_behalf=True,
    )


def warm_tenant(db: Session, tenant_id: str) -> dict:
    rc = cache()
    ctx = _system_ctx(tenant_id)
    rs = ReportService(db)
    datamart_key = rs._datamart_key(tenant_id)
    snapshot = cached_snapshot_ref(ctx, datamart_key)
    if not rc.enabled or not snapshot:
        log.info("cache_warm_noop", tenant_id=tenant_id, cache_enabled=rc.enabled, has_snapshot=bool(snapshot))
        return {"templates": 0, "warmed": 0, "skipped": 0}

    templates = db.query(ReportTemplate).all()
    warmed = skipped = 0
    for t in templates:
        try:
            resolved = rs._resolve_published(ctx, t.id)
            if any(p.required for p in resolved.data_spec.runtime_params):
                skipped += 1
                continue
            catalog = rs.semantic.get_pinned_catalog(tenant_id, resolved.semantic_version_ref)
            run_query(
                ctx=ctx, datamart_key=datamart_key, spec=resolved.data_spec,
                catalog=catalog, params={}, snapshot_ref=snapshot, use_cache=True,
            )
            warmed += 1
        except Exception as exc:  # noqa: BLE001
            skipped += 1
            log.info("cache_warm_skip", tenant_id=tenant_id, template_id=t.id, error=str(exc)[:120])
    log.info("cache_warm_tenant", tenant_id=tenant_id, warmed=warmed, skipped=skipped, total=len(templates))
    return {"templates": len(templates), "warmed": warmed, "skipped": skipped}


def warm_all_active() -> dict:
    pg = get_postgres_database().session()
    total = 0
    try:
        pg.execute(text("SET search_path TO platform, public"))
        tenants = list_active_tenants(pg)
    finally:
        pg.close()

    for row in tenants:
        try:
            with worker_pg_session(row.subdomain) as db:
                total += warm_tenant(db, row.subdomain)["warmed"]
        except Exception as exc:  # noqa: BLE001
            log.error("cache_warm_tenant_failed", tenant_id=row.subdomain, error=str(exc))
    return {"warmed": total}
