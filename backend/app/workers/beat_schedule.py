"""Celery Beat — dispatch enabled report schedules."""

from __future__ import annotations

from celery.schedules import crontab

from app.core.logging import get_logger
from app.db.metadata import ReportSchedule
from app.db.pg_tenant_session import worker_pg_session
from app.db.postgres import get_postgres_database
from app.repositories.tenant_provision import list_active_tenants
from app.workers.celery_app import celery_app
from app.workers.tasks import refresh_semantic_catalogs, run_scheduled_report, warm_result_cache
from sqlalchemy import text

log = get_logger(__name__)


@celery_app.on_after_configure.connect
def setup_periodic_dispatch(sender, **_kwargs):  # noqa: ANN001
    sender.add_periodic_task(crontab(minute="*"), dispatch_due_schedules.s(), name="dispatch-schedules")
    sender.add_periodic_task(
        crontab(hour=2, minute=30), refresh_semantic_catalogs.s(), name="nightly-semantic-refresh"
    )
    sender.add_periodic_task(
        crontab(hour=3, minute=0), warm_result_cache.s(), name="nightly-cache-warm"
    )


@celery_app.task
def dispatch_due_schedules() -> int:
    pg = get_postgres_database().session()
    count = 0
    try:
        pg.execute(text("SET search_path TO platform, public"))
        tenants = list_active_tenants(pg)
    finally:
        pg.close()

    for row in tenants:
        with worker_pg_session(row.subdomain) as db:
            enabled = db.query(ReportSchedule).filter(ReportSchedule.enabled.is_(True)).all()
            for schedule in enabled:
                run_scheduled_report.delay(schedule.id, row.subdomain)
                count += 1
    log.info("schedules_dispatched", count=count)
    return count
