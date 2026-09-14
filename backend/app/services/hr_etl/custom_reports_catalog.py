"""Custom report metadata in hrm_control.tenant_custom_reports (application DB)."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from threading import Lock
from typing import Literal, Optional

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.core.warehouse import get_platform_engine_sync

logger = logging.getLogger("custom_reports.catalog")

_DEFINITIONS_CACHE_TTL_SEC = 120
_definitions_cache: dict[str, tuple[float, list["TenantCustomReportRow"]]] = {}
_definitions_cache_lock = Lock()

ReportType = Literal["table", "payslip"]
ReportSource = Literal["dbt", "sync"]

_SELECT = """
    SELECT id, tenant_id, module, report_name, view_name, view_query,
           report_type, source, sort_order, is_active, is_system,
           period_year_column, period_month_column
    FROM hrm_control.tenant_custom_reports
    WHERE tenant_id = :tid AND is_active = TRUE
    ORDER BY sort_order ASC, report_name ASC, view_name ASC
"""

_INSERT_FROM_TEMPLATE = """
    INSERT INTO hrm_control.tenant_custom_reports
        (tenant_id, module, report_name, view_name, view_query,
         report_type, source, sort_order, is_active, is_system,
         period_year_column, period_month_column)
    SELECT
        :tenant_id, t.module, t.report_name, t.view_name, t.view_query,
        t.report_type, 'sync', t.sort_order, TRUE, t.is_system,
        t.period_year_column, t.period_month_column
    FROM hrm_control.custom_report_templates t
    ON CONFLICT (tenant_id, view_name) DO NOTHING
"""


@dataclass(frozen=True)
class TenantCustomReportRow:
    id: int
    tenant_id: str
    module: str
    report_name: str
    view_name: str
    view_query: Optional[str]
    report_type: ReportType
    source: ReportSource
    sort_order: int
    is_active: bool
    is_system: bool = False
    period_year_column: Optional[str] = None
    period_month_column: Optional[str] = None

    @property
    def is_payslip(self) -> bool:
        return self.report_type == "payslip"

    @property
    def needs_sync(self) -> bool:
        return bool((self.view_query or "").strip())


def _row_to_dataclass(row: dict) -> TenantCustomReportRow:
    return TenantCustomReportRow(
        id=int(row["id"]),
        tenant_id=row["tenant_id"],
        module=row["module"],
        report_name=row["report_name"],
        view_name=row["view_name"],
        view_query=row.get("view_query"),
        report_type=row.get("report_type") or "table",
        source=row.get("source") or "sync",
        sort_order=int(row.get("sort_order") or 0),
        is_active=bool(row.get("is_active", True)),
        is_system=bool(row.get("is_system", False)),
        period_year_column=row.get("period_year_column"),
        period_month_column=row.get("period_month_column"),
    )


def _is_missing_table(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return "tenant_custom_reports" in msg and (
        "does not exist" in msg or "undefinedtable" in msg or "undefined table" in msg
    )


def _filter_module(
    rows: list[TenantCustomReportRow], module: str | None
) -> list[TenantCustomReportRow]:
    if not module or not module.strip():
        return rows
    key = module.strip().lower()
    return [row for row in rows if row.module.lower() == key]


def invalidate_report_definitions_cache(tenant_id: str | None = None) -> None:
    """Drop cached catalog rows after admin mutations or explicit sync."""
    with _definitions_cache_lock:
        if tenant_id is None:
            _definitions_cache.clear()
        else:
            _definitions_cache.pop(tenant_id.strip(), None)


def load_report_definitions_sync(
    tenant_id: str,
    *,
    module: str | None = None,
    pg: Engine | None = None,
    use_cache: bool = True,
) -> list[TenantCustomReportRow]:
    tid = tenant_id.strip()
    if use_cache and pg is None and module is None:
        now = time.monotonic()
        with _definitions_cache_lock:
            cached = _definitions_cache.get(tid)
            if cached and now - cached[0] < _DEFINITIONS_CACHE_TTL_SEC:
                return list(cached[1])

    eng = pg or get_platform_engine_sync()
    try:
        with eng.connect() as conn:
            rows = conn.execute(text(_SELECT), {"tid": tid}).mappings().all()
    except Exception as exc:
        if _is_missing_table(exc):
            logger.warning("tenant_custom_reports missing — falling back to warehouse discovery")
            return []
        raise
    result = [_row_to_dataclass(dict(r)) for r in rows]
    if use_cache and pg is None and module is None:
        with _definitions_cache_lock:
            _definitions_cache[tid] = (time.monotonic(), list(result))
    return _filter_module(result, module)


def load_report_definitions_async(
    db: Session,
    tenant_id: str,
    *,
    module: str | None = None,
) -> list[TenantCustomReportRow]:
    try:
        result = db.execute(text(_SELECT), {"tid": tenant_id})
        rows = [_row_to_dataclass(dict(r)) for r in result.mappings().all()]
    except Exception as exc:
        if _is_missing_table(exc):
            return []
        raise
    return _filter_module(rows, module)


def get_report_definition_sync(
    tenant_id: str,
    view_name: str,
    *,
    pg: Engine | None = None,
) -> TenantCustomReportRow | None:
    key = view_name.strip().lower()
    rows = load_report_definitions_sync(tenant_id, pg=pg, use_cache=pg is None)
    for row in rows:
        if row.view_name.lower() == key:
            return row
    return None


def ensure_default_reports_sync(tenant_id: str, *, pg: Engine | None = None) -> int:
    """Copy platform report templates into tenant_custom_reports. Returns rows inserted."""
    eng = pg or get_platform_engine_sync()
    with eng.begin() as conn:
        result = conn.execute(
            text(_INSERT_FROM_TEMPLATE),
            {"tenant_id": tenant_id},
        )
    invalidate_report_definitions_cache(tenant_id)
    return result.rowcount or 0


def ensure_default_reports_async(db: Session, tenant_id: str) -> int:
    result = db.execute(text(_INSERT_FROM_TEMPLATE), {"tenant_id": tenant_id})
    db.commit()
    return result.rowcount or 0
