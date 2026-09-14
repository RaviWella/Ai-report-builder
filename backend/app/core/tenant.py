"""Warehouse layer lifecycle — schemas inside each tenant's Postgres database."""
from __future__ import annotations

import logging
from typing import List

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.warehouse import (
    WarehouseLayout,
    control_schema_ddl,
    get_layout_sync,
)

logger = logging.getLogger("tenant")

_WAREHOUSE_LAYERS_READY: set[str] = set()


def is_warehouse_layers_ready(tenant_id: str) -> bool:
    return tenant_id in _WAREHOUSE_LAYERS_READY


def mark_warehouse_layers_ready(tenant_id: str) -> None:
    _WAREHOUSE_LAYERS_READY.add(tenant_id)


def invalidate_warehouse_layers_ready(tenant_id: str) -> None:
    _WAREHOUSE_LAYERS_READY.discard(tenant_id)


SCHEMA_SUFFIXES = ["_hr_raw", "_hr", "_hr_semantic", "_hr_control"]

MART_TABLES = [
    "database_connections",
    "data_access_rules",
]


class TenantManager:
    def schema_exists(self, session: Session, schema_name: str) -> bool:
        result = session.execute(
            text(
                "SELECT EXISTS("
                "  SELECT 1 FROM information_schema.schemata WHERE schema_name = :name"
                ")"
            ),
            {"name": schema_name},
        )
        return bool(result.scalar())

    def create_schema(self, session: Session, schema_name: str) -> None:
        session.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"'))
        session.commit()

    def table_exists_in_schema(
        self, session: Session, schema_name: str, table_name: str
    ) -> bool:
        result = session.execute(
            text(
                "SELECT EXISTS("
                "  SELECT 1 FROM information_schema.tables"
                "  WHERE table_schema = :schema AND table_name = :table"
                ")"
            ),
            {"schema": schema_name, "table": table_name},
        )
        return bool(result.scalar())

    def clone_table_from_public(
        self, session: Session, schema_name: str, table_name: str
    ) -> None:
        session.execute(
            text(
                f'CREATE TABLE IF NOT EXISTS "{schema_name}"."{table_name}" '
                f'(LIKE public."{table_name}" INCLUDING ALL)'
            )
        )

    def ensure_mart_tables_exist(
        self, session: Session, tenant_id: str, layout: WarehouseLayout
    ) -> None:
        from app.core.mart_metadata import ensure_mart_metadata_tables

        mart = layout.mart_schema
        if not self.schema_exists(session, mart):
            return
        conn = session.connection()
        created = ensure_mart_metadata_tables(conn, mart)
        if created:
            session.commit()

    def ensure_warehouse_layers(
        self,
        session: Session,
        tenant_id: str,
        layout: WarehouseLayout,
        *,
        force: bool = False,
    ) -> bool:
        if not force and is_warehouse_layers_ready(tenant_id):
            return False

        created = False
        for schema in (
            layout.raw_schema,
            layout.mart_schema,
            layout.semantic_schema,
            layout.custom_reports_schema,
            layout.control_schema,
            layout.snap_schema,
        ):
            if not self.schema_exists(session, schema):
                logger.info("Creating schema %s for %s", schema, tenant_id)
                self.create_schema(session, schema)
                created = True
        self._ensure_control_tables(session, layout.control_schema)
        self.ensure_mart_tables_exist(session, tenant_id, layout)
        mark_warehouse_layers_ready(tenant_id)
        if created:
            logger.info("Warehouse layers initialized for tenant %s", tenant_id)
        return created

    def ensure_schemas_exist(
        self, session: Session, tenant_id: str, *, force: bool = False
    ) -> bool:
        return self.ensure_warehouse_layers(
            session, tenant_id, get_layout_sync(tenant_id), force=force
        )

    def _ensure_control_tables(self, session: Session, control_schema: str) -> None:
        for stmt in control_schema_ddl(control_schema):
            session.execute(text(stmt))
        session.commit()

    def list_tenants(self, session: Session) -> List[str]:
        result = session.execute(
            text(
                "SELECT tenant_id FROM hrm_control.tenant_registry"
                " WHERE is_active = TRUE ORDER BY tenant_id"
            )
        )
        return [row[0] for row in result.fetchall()]


tenant_manager = TenantManager()
