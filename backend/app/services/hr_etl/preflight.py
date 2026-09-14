"""Synchronous checks before accepting an ETL run (fail fast, clear errors)."""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text

from app.core.warehouse import get_warehouse_engine_sync
from app.services.hr_etl.errors import format_run_error
from app.services.source_databases import build_engine_for_etl_source
from app.services.tenant_etl_sources import load_sources_for_etl

logger = logging.getLogger("hr_etl.preflight")


def preflight_etl_sources(platform_pg, tenant_id: str) -> list[dict[str, Any]]:
    """
    Verify each configured source can load credentials and open a connection.
    Returns a list of per-source errors (empty when ready).
    """
    sources = load_sources_for_etl(platform_pg, tenant_id)
    if not sources:
        return [
            {
                "source_key": None,
                "display_name": None,
                "error": (
                    f"No ETL sources configured for tenant '{tenant_id}'. "
                    "Add sources under Settings → ETL Sources."
                ),
            }
        ]

    warehouse = get_warehouse_engine_sync(tenant_id, provision=False)
    errors: list[dict[str, Any]] = []

    for src in sources:
        label = src.display_name or src.source_key
        try:
            engine, _config = build_engine_for_etl_source(tenant_id, src)
            try:
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
            finally:
                engine.dispose()
        except Exception as exc:
            logger.warning(
                "ETL preflight failed tenant=%s source=%s: %s",
                tenant_id,
                src.source_key,
                exc,
            )
            errors.append(
                {
                    "source_key": src.source_key,
                    "display_name": label,
                    "error": format_run_error(exc),
                }
            )

    return errors
