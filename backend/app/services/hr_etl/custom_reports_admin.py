"""CRUD for hrm_control.tenant_custom_reports."""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas.custom_reports import (
    CustomReportDefinitionCreate,
    CustomReportDefinitionOut,
    CustomReportDefinitionUpdate,
)
from app.services.hr_etl.custom_reports_catalog import (
    TenantCustomReportRow,
    _row_to_dataclass,
    invalidate_report_definitions_cache,
)
from app.services.hr_etl.custom_reports_data import (
    _validate_view_name,
    invalidate_view_columns_cache,
)
from app.services.hr_etl.custom_reports_sync import (
    CustomReportSyncReport,
    sync_tenant_custom_report_views,
    validate_view_query,
)
from app.services.hr_etl.schema_names import custom_reports_schema

logger = logging.getLogger("custom_reports.admin")

_SELECT_BY_TENANT = """
    SELECT id, tenant_id, module, report_name, view_name, view_query,
           report_type, source, sort_order, is_active, is_system,
           period_year_column, period_month_column
    FROM hrm_control.tenant_custom_reports
    WHERE tenant_id = :tid
    {active_filter}
    ORDER BY sort_order ASC, report_name ASC, view_name ASC
"""

_SELECT_BY_ID = """
    SELECT id, tenant_id, module, report_name, view_name, view_query,
           report_type, source, sort_order, is_active, is_system,
           period_year_column, period_month_column
    FROM hrm_control.tenant_custom_reports
    WHERE tenant_id = :tid AND id = :id
"""

_INSERT = """
    INSERT INTO hrm_control.tenant_custom_reports
        (tenant_id, module, report_name, view_name, view_query,
         report_type, source, sort_order, is_active)
    VALUES
        (:tenant_id, :module, :report_name, :view_name, :view_query,
         :report_type, 'sync', :sort_order, TRUE)
    RETURNING id, tenant_id, module, report_name, view_name, view_query,
              report_type, source, sort_order, is_active
"""


def row_to_out(row: TenantCustomReportRow) -> CustomReportDefinitionOut:
    return CustomReportDefinitionOut(
        id=row.id,
        tenant_id=row.tenant_id,
        module=row.module,
        report_name=row.report_name,
        view_name=row.view_name,
        view_query=row.view_query,
        report_type=row.report_type,
        source=row.source,
        sort_order=row.sort_order,
        is_active=row.is_active,
        is_system=row.is_system,
        period_year_column=row.period_year_column,
        period_month_column=row.period_month_column,
    )


def _map_row(raw: dict[str, Any]) -> TenantCustomReportRow:
    return _row_to_dataclass(raw)


def list_definitions(
    db: Session,
    tenant_id: str,
    *,
    include_inactive: bool = False,
    module: str | None = None,
) -> list[CustomReportDefinitionOut]:
    active_filter = "" if include_inactive else "AND is_active = TRUE"
    sql = _SELECT_BY_TENANT.format(active_filter=active_filter)
    result = db.execute(text(sql), {"tid": tenant_id})
    rows = [_map_row(dict(r)) for r in result.mappings().all()]
    if module and module.strip():
        key = module.strip().lower()
        rows = [row for row in rows if row.module.lower() == key]
    return [row_to_out(row) for row in rows]


def get_definition(
    db: Session, tenant_id: str, report_id: int
) -> CustomReportDefinitionOut | None:
    result = db.execute(
        text(_SELECT_BY_ID), {"tid": tenant_id, "id": report_id}
    )
    row = result.mappings().first()
    if not row:
        return None
    return row_to_out(_map_row(dict(row)))


def create_definition(
    db: Session,
    tenant_id: str,
    payload: CustomReportDefinitionCreate,
) -> CustomReportDefinitionOut:
    view_name = payload.view_name.strip()
    _validate_view_name(view_name)
    validate_view_query(payload.view_query.strip())

    result = db.execute(
        text(_INSERT),
        {
            "tenant_id": tenant_id,
            "module": payload.module.strip(),
            "report_name": payload.report_name.strip(),
            "view_name": view_name,
            "view_query": payload.view_query.strip(),
            "report_type": payload.report_type,
            "sort_order": payload.sort_order,
        },
    )
    db.commit()
    row = result.mappings().first()
    if not row:
        raise RuntimeError("Failed to create custom report definition")
    created = row_to_out(_map_row(dict(row)))
    _sync_after_mutation(tenant_id, view_name=view_name)
    return created


def update_definition(
    db: Session,
    tenant_id: str,
    report_id: int,
    payload: CustomReportDefinitionUpdate,
) -> CustomReportDefinitionOut:
    existing = get_definition(db, tenant_id, report_id)
    if not existing:
        raise LookupError(f"Report definition not found: {report_id}")

    updates: dict[str, Any] = {}
    if payload.module is not None:
        updates["module"] = payload.module.strip()
    if payload.report_name is not None:
        updates["report_name"] = payload.report_name.strip()
    if payload.view_query is not None:
        validate_view_query(payload.view_query.strip())
        updates["view_query"] = payload.view_query.strip()
    if payload.report_type is not None:
        updates["report_type"] = payload.report_type
    if payload.sort_order is not None:
        updates["sort_order"] = payload.sort_order
    if payload.is_active is not None:
        updates["is_active"] = payload.is_active

    if not updates:
        return existing

    set_clause = ", ".join(f"{key} = :{key}" for key in updates)
    updates["id"] = report_id
    updates["tenant_id"] = tenant_id

    db.execute(
        text(
            f"""
            UPDATE hrm_control.tenant_custom_reports
            SET {set_clause}, updated_at = NOW()
            WHERE id = :id AND tenant_id = :tenant_id
            """
        ),
        updates,
    )
    db.commit()

    updated = get_definition(db, tenant_id, report_id)
    if not updated:
        raise RuntimeError("Report definition missing after update")
    if updated.view_query:
        _sync_after_mutation(tenant_id, view_name=updated.view_name)
    else:
        invalidate_report_definitions_cache(tenant_id)
    return updated


def delete_definition(
    db: Session, tenant_id: str, report_id: int
) -> None:
    existing = get_definition(db, tenant_id, report_id)
    if not existing:
        raise LookupError(f"Report definition not found: {report_id}")
    db.execute(
        text(
            """
            DELETE FROM hrm_control.tenant_custom_reports
            WHERE id = :id AND tenant_id = :tenant_id
            """
        ),
        {"id": report_id, "tenant_id": tenant_id},
    )
    db.commit()
    _drop_sync_view(tenant_id, existing.view_name)
    _sync_after_mutation(tenant_id)


def run_sync(tenant_id: str) -> CustomReportSyncReport:
    return sync_tenant_custom_report_views(tenant_id, ensure_defaults=True)


def _sync_after_mutation(tenant_id: str, *, view_name: str | None = None) -> None:
    report = run_sync(tenant_id)
    invalidate_report_definitions_cache(tenant_id)
    invalidate_view_columns_cache(tenant_id)
    if report.errors:
        logger.warning(
            "Custom report sync after mutation tenant=%s errors=%s",
            tenant_id,
            report.errors,
        )
        if view_name:
            prefix = f"{view_name}:"
            relevant = [err for err in report.errors if err.startswith(prefix)]
            if relevant:
                raise ValueError("; ".join(relevant))


def _drop_sync_view(tenant_id: str, view_name: str) -> None:
    from app.core.warehouse import get_warehouse_engine_sync

    schema = custom_reports_schema(tenant_id)
    try:
        wh = get_warehouse_engine_sync(tenant_id, provision=False)
        with wh.begin() as conn:
            conn.execute(text(f'DROP VIEW IF EXISTS "{schema}"."{view_name}"'))
    except Exception as exc:
        logger.warning(
            "Failed to drop custom report view tenant=%s view=%s (%s)",
            tenant_id,
            view_name,
            exc,
        )
