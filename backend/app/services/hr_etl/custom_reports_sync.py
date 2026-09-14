"""Sync tenant custom report views from application DB metadata into the warehouse."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.core.warehouse import get_layout_sync, get_warehouse_engine_sync
from app.services.hr_etl.custom_reports_catalog import (
    TenantCustomReportRow,
    ensure_default_reports_sync,
    load_report_definitions_sync,
)
from app.services.hr_etl.custom_reports_data import _validate_view_name
from app.services.hr_etl.schema_names import custom_reports_schema

logger = logging.getLogger("custom_reports.sync")

_FORBIDDEN_SQL = re.compile(
    r"\b(insert|update|delete|drop|alter|create|grant|revoke|truncate|execute|copy)\b",
    re.IGNORECASE,
)


@dataclass
class CustomReportSyncReport:
    tenant_id: str
    schema: str
    created: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def render_view_query(query: str, tenant_id: str) -> str:
    layout = get_layout_sync(tenant_id)
    replacements = {
        "{mart_schema}": f'"{layout.mart_schema}"',
        "{semantic_schema}": f'"{layout.semantic_schema}"',
        "{raw_schema}": f'"{layout.raw_schema}"',
        "{custom_reports_schema}": f'"{layout.custom_reports_schema}"',
        "{control_schema}": f'"{layout.control_schema}"',
        "{snap_schema}": f'"{layout.snap_schema}"',
        "{tenant_id}": tenant_id.replace("'", "''"),
    }
    rendered = query.strip()
    for token, value in replacements.items():
        rendered = rendered.replace(token, value)
    return rendered


def validate_view_query(sql: str) -> None:
    body = sql.strip().rstrip(";")
    if not body:
        raise ValueError("view_query is empty")
    lowered = body.lower()
    if not (lowered.startswith("select") or lowered.startswith("with")):
        raise ValueError("view_query must start with SELECT or WITH")
    if ";" in body:
        raise ValueError("view_query must not contain semicolons")
    if _FORBIDDEN_SQL.search(body):
        raise ValueError("view_query contains forbidden SQL keywords")


def _apply_view(
    conn,
    schema: str,
    row: TenantCustomReportRow,
    report: CustomReportSyncReport,
) -> None:
    if not row.needs_sync:
        report.skipped.append(row.view_name)
        return
    assert row.view_query is not None
    _validate_view_name(row.view_name)
    rendered = render_view_query(row.view_query, row.tenant_id)
    validate_view_query(rendered)
    ddl = f'CREATE OR REPLACE VIEW "{schema}"."{row.view_name}" AS {rendered}'
    conn.execute(text(ddl))
    report.created.append(row.view_name)
    logger.info(
        "Synced custom report view tenant=%s view=%s",
        row.tenant_id,
        row.view_name,
    )


def sync_tenant_custom_report_views(
    tenant_id: str,
    *,
    pg: Engine | None = None,
    platform_pg: Engine | None = None,
    ensure_defaults: bool = True,
) -> CustomReportSyncReport:
    """Create or replace warehouse views for source=sync rows with view_query."""
    tid = tenant_id.strip()
    schema = custom_reports_schema(tid)
    report = CustomReportSyncReport(tenant_id=tid, schema=schema)

    if ensure_defaults:
        try:
            ensure_default_reports_sync(tid, pg=platform_pg)
        except Exception as exc:
            if "tenant_custom_reports" not in str(exc).lower():
                report.errors.append(f"ensure_defaults: {exc}")
                return report

    wh = pg or get_warehouse_engine_sync(tid, provision=True)
    rows = load_report_definitions_sync(tid, pg=platform_pg)
    sync_rows = [row for row in rows if row.needs_sync]
    if not sync_rows:
        return report

    try:
        with wh.begin() as conn:
            conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
            for row in sync_rows:
                try:
                    _apply_view(conn, schema, row, report)
                except (ValueError, Exception) as exc:
                    msg = f"{row.view_name}: {exc}"
                    logger.warning("Custom report sync failed: %s", msg)
                    report.errors.append(msg)
    except Exception as exc:
        report.errors.append(str(exc))

    return report
