"""WS-3 — datamart freshness / snapshot reference.

Reads a single load-watermark scalar from the tenant's datamart (configurable
query) and renders it as a compact, comparable `datamart_snapshot_ref` string.
Best-effort: any failure (VPN down, column absent) returns None so a run is never
blocked by freshness reading.
"""

from __future__ import annotations

import datetime as _dt

from sqlalchemy import text

from app.core.config import settings
from app.core.logging import get_logger
from app.core.tenancy import TenantContext
from app.db.datamart import datamart_connection
from app.query_engine import guards

log = get_logger(__name__)


def read_snapshot_ref(ctx: TenantContext, datamart_key: str) -> str | None:
    query = settings.datamart_watermark_query.strip()
    if not query:
        return None
    try:
        guards.assert_select_only(query)
        with datamart_connection(ctx, datamart_key) as conn:
            value = conn.execute(text(query)).scalar()
    except Exception as exc:  # noqa: BLE001 - never break a run on freshness
        log.warning("datamart_snapshot_read_failed", datamart_key=datamart_key, error=str(exc)[:160])
        return None
    if value is None:
        return None
    if isinstance(value, _dt.datetime):
        return value.strftime("%Y%m%d%H%M%S")
    return str(value)[:128]
