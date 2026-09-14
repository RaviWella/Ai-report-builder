"""Ensure staging tables exist in the tenant warehouse raw layer."""
from __future__ import annotations

import logging
from typing import Set

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.core.warehouse import get_layout_sync
from app.services.hr_etl.staging_ddl import STAGING_ALTER_DDL, STAGING_DDL

logger = logging.getLogger("hr_etl.staging_schema")

_ensured: Set[str] = set()


def ensure_staging_tables(pg: Engine, tenant_id: str, *, force: bool = False) -> None:
    if not force and tenant_id in _ensured:
        return
    layout = get_layout_sync(tenant_id)
    schema = layout.raw_schema
    with pg.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
        for ddl in STAGING_DDL:
            conn.execute(text(ddl.format(schema=schema)))
        for ddl in STAGING_ALTER_DDL:
            conn.execute(text(ddl.format(schema=schema)))
    _ensured.add(tenant_id)
    logger.info("Ensured staging tables in %s (tenant=%s)", schema, tenant_id)
