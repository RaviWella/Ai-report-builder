"""Async tasks: scheduled report runs + async exports + email delivery."""

from __future__ import annotations

from app.core.logging import get_logger
from app.core.tenancy import TenantContext
from app.db.metadata import ReportSchedule, ReportTemplate
from app.db.pg_tenant_session import worker_pg_session
from app.db.postgres import get_postgres_database
from app.domain.enums import AuditAction, ExportFormat, Role
from app.repositories.tenant_provision import list_active_tenants
from app.services.audit_service import AuditService
from app.services.report_service import ReportService
from app.tenancy.pg_schema import subdomain_to_pg_schema
from app.workers.celery_app import celery_app
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


@celery_app.task(bind=True, max_retries=3, default_retry_delay=300)
def run_scheduled_report(self, schedule_id: str, tenant_id: str) -> dict:  # noqa: ANN001
    with worker_pg_session(tenant_id) as db:
        try:
            schedule = db.get(ReportSchedule, schedule_id)
            if schedule is None or not schedule.enabled:
                return {"skipped": True, "schedule_id": schedule_id}
            template = db.get(ReportTemplate, schedule.template_id)
            if template is None:
                return {"skipped": True, "reason": "template_missing"}

            ctx = _system_ctx(tenant_id)
            report = ReportService(db)
            fmt = ExportFormat(schedule.format)
            content, mime = report.export(ctx, template.id, schedule.runtime_params or {}, fmt)

            for recipient in schedule.recipients or []:
                deliver_email(recipient, template.name, content, mime, fmt)

            AuditService(db).log(
                user_id="system",
                action=AuditAction.SCHEDULE_TRIGGERED,
                target_type="schedule",
                target_id=schedule_id,
                detail={"recipients": len(schedule.recipients or []), "format": fmt.value},
            )
            return {"ok": True, "bytes": len(content)}
        except Exception as exc:
            log.error("scheduled_report_failed", schedule_id=schedule_id, error=str(exc))
            raise self.retry(exc=exc) from exc


@celery_app.task
def refresh_semantic_catalogs() -> dict:
    from app.services.semantic_service import SemanticService

    pg = get_postgres_database().session()
    refreshed = 0
    try:
        pg.execute(text("SET search_path TO platform, public"))
        tenants = list_active_tenants(pg)
    finally:
        pg.close()

    for row in tenants:
        try:
            with worker_pg_session(row.subdomain) as db:
                svc = SemanticService(db)
                new_version = svc.refresh_if_changed(row.subdomain, row.datamart_key)
                if new_version:
                    refreshed += 1
        except Exception as exc:
            log.error("semantic_refresh_failed", tenant_id=row.subdomain, error=str(exc))
    log.info("semantic_refresh_run", tenants_refreshed=refreshed)
    return {"refreshed": refreshed}


@celery_app.task
def warm_result_cache() -> dict:
    from app.services.cache_warm import warm_all_active

    result = warm_all_active()
    log.info("cache_warm_run", warmed=result.get("warmed", 0))
    return result


@celery_app.task
def async_export(template_id: str, tenant_id: str, params: dict, fmt: str) -> dict:
    with worker_pg_session(tenant_id) as db:
        ctx = _system_ctx(tenant_id)
        content, _mime = ReportService(db).export(ctx, template_id, params, ExportFormat(fmt))
        return {"ok": True, "bytes": len(content)}


def deliver_email(recipient: str, report_name: str, content: bytes, mime: str, fmt: ExportFormat) -> None:
    log.info(
        "email_delivery_stub",
        recipient=recipient,
        report=report_name,
        mime=mime,
        format=fmt.value,
        bytes=len(content),
    )
