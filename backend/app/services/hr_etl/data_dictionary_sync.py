"""Refresh warehouse-resident data dictionary after ETL / dbt (auto-discovery)."""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.engine import Engine

from app.core.config import settings
from app.core.warehouse import get_warehouse_engine_sync
from app.services.hr_etl.data_dictionary_schema import sync_warehouse_dictionary

logger = logging.getLogger("hr_etl.data_dictionary")


def refresh_warehouse_data_dictionary(
    tenant_id: str,
    *,
    warehouse_engine: Engine | None = None,
) -> dict[str, int]:
    """
    Introspect current warehouse schemas and reload hr_control.data_dictionary_*.

    Called automatically after successful dbt when SYNC_DATA_DICTIONARY_ON_ETL=true.
    Picks up new source staging tables (hr_raw.stg_*) and new mart objects (hr.*).
    """
    from tools.data_dictionary.generator import build_catalog

    wh = warehouse_engine or get_warehouse_engine_sync(tenant_id)
    objects, _dbt_meta, er_meta = build_catalog(wh, tenant_id)
    counts = sync_warehouse_dictionary(wh, tenant_id, objects, er_meta)
    if counts.get("skipped"):
        logger.warning(
            "Data dictionary sync skipped tenant=%s reason=%s",
            tenant_id,
            counts.get("reason"),
        )
    else:
        logger.info(
            "Data dictionary synced tenant=%s objects=%d fields=%d",
            tenant_id,
            counts["warehouse_objects"],
            counts["warehouse_fields"],
        )
    return counts


def maybe_sync_after_etl(
    tenant_id: str,
    *,
    dbt_succeeded: bool,
    warehouse_engine: Engine | None = None,
) -> dict[str, Any]:
    """Sync dictionary when enabled and dbt completed successfully."""
    if not dbt_succeeded:
        return {"skipped": True, "reason": "dbt_not_successful"}
    if not settings.SYNC_DATA_DICTIONARY_ON_ETL:
        return {"skipped": True, "reason": "disabled"}
    try:
        counts = refresh_warehouse_data_dictionary(
            tenant_id, warehouse_engine=warehouse_engine
        )
        return {"skipped": False, **counts}
    except Exception as exc:
        logger.exception(
            "Data dictionary sync failed tenant=%s (ETL continues)",
            tenant_id,
        )
        return {"skipped": False, "error": str(exc)}
