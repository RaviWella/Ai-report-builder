"""Create tenant PostgreSQL schemas by cloning table structures from public."""

from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import Settings, settings
from app.core.exceptions import PostgresSchemaError
from app.db.pg_tenant_db import clone_foreign_keys, schema_lock_id, seed_tenant_alembic_version
from app.db.pg_template_seeds import copy_template_seed_rows
from app.tenancy.pg_schema import validate_pg_schema_name, validate_template_schema

logger = logging.getLogger(__name__)

_TABLE_LIKE = (
    "INCLUDING DEFAULTS INCLUDING CONSTRAINTS INCLUDING INDEXES "
    "INCLUDING STORAGE INCLUDING COMMENTS"
)


class PostgresSchemaProvisioner:
    """Ensure a tenant schema exists by copying base-table DDL from public."""

    def __init__(self, cfg: Settings | None = None) -> None:
        cfg = cfg or settings
        self._template_schema = validate_template_schema(cfg.pg_template_schema)
        self._ready_schemas: set[str] = set()

    def remember_schema(self, schema_name: str) -> None:
        self._ready_schemas.add(schema_name)

    def forget_schema(self, schema_name: str | None = None) -> None:
        if schema_name is None:
            self._ready_schemas.clear()
        else:
            self._ready_schemas.discard(schema_name)

    def ensure_schema(self, session: Session, schema_name: str) -> bool:
        safe_schema = validate_pg_schema_name(schema_name)
        if safe_schema == self._template_schema:
            raise PostgresSchemaError(
                f"Tenant schema cannot be the template schema ({self._template_schema!r})"
            )

        if safe_schema in self._ready_schemas:
            return False

        if self.schema_exists(session, safe_schema):
            self.remember_schema(safe_schema)
            return False

        lock_id = schema_lock_id(safe_schema)
        session.execute(text("SELECT pg_advisory_lock(:key)"), {"key": lock_id})
        try:
            if self.schema_exists(session, safe_schema):
                self.remember_schema(safe_schema)
                return False
            self._create_schema_from_template(session, safe_schema)
            self.remember_schema(safe_schema)
            logger.info(
                "Provisioned PostgreSQL schema from %s",
                self._template_schema,
                extra={"schema": safe_schema},
            )
            return True
        finally:
            session.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": lock_id})

    def schema_exists(self, session: Session, schema_name: str) -> bool:
        safe_schema = validate_pg_schema_name(schema_name)
        exists = session.execute(
            text(
                "SELECT 1 FROM information_schema.schemata "
                "WHERE schema_name = :schema_name"
            ),
            {"schema_name": safe_schema},
        ).scalar_one_or_none()
        return exists is not None

    def _create_schema_from_template(self, session: Session, target_schema: str) -> None:
        tpl = self._template_schema
        session.execute(text(f'CREATE SCHEMA "{target_schema}"'))

        tables = session.execute(
            text(
                "SELECT table_name "
                "FROM information_schema.tables "
                "WHERE table_schema = :template_schema AND table_type = 'BASE TABLE' "
                "AND table_name NOT LIKE 'alembic_version%' "
                "ORDER BY table_name"
            ),
            {"template_schema": tpl},
        ).scalars().all()

        if not tables:
            raise PostgresSchemaError(
                f"Template schema {tpl!r} has no tables to clone into {target_schema!r}. "
                "Run Alembic migrations first."
            )

        for table_name in tables:
            try:
                session.execute(
                    text(
                        f'CREATE TABLE "{target_schema}"."{table_name}" '
                        f'(LIKE "{tpl}"."{table_name}" {_TABLE_LIKE})'
                    ),
                )
                self._rebind_serial_defaults(session, target_schema, table_name)
            except Exception as exc:
                logger.warning("Could not clone table %s: %s", table_name, exc)

        clone_foreign_keys(session, source_schema=tpl, target_schema=target_schema)
        copy_template_seed_rows(session, source_schema=tpl, target_schema=target_schema)
        seed_tenant_alembic_version(session, target_schema)

    def _rebind_serial_defaults(self, session: Session, target_schema: str, table_name: str) -> None:
        tpl = self._template_schema
        serial_columns = session.execute(
            text(
                """
                SELECT a.attname AS column_name
                FROM pg_attribute a
                JOIN pg_class c ON a.attrelid = c.oid
                JOIN pg_namespace n ON c.relnamespace = n.oid
                WHERE n.nspname = :template_schema
                  AND c.relname = :table_name
                  AND a.attnum > 0
                  AND NOT a.attisdropped
                  AND pg_get_serial_sequence(
                        quote_ident(:template_schema) || '.' || quote_ident(:table_name),
                        a.attname
                      ) IS NOT NULL
                """
            ),
            {"template_schema": tpl, "table_name": table_name},
        ).scalars().all()

        for column_name in serial_columns:
            sequence_name = f"{table_name}_{column_name}_seq"
            session.execute(text(f'CREATE SEQUENCE "{target_schema}"."{sequence_name}"'))
            session.execute(
                text(
                    f'ALTER TABLE "{target_schema}"."{table_name}" '
                    f'ALTER COLUMN "{column_name}" '
                    f"SET DEFAULT nextval("
                    f"""'"{target_schema}"."{sequence_name}"'::regclass)"""
                ),
            )
            session.execute(
                text(f"SELECT setval('\"{target_schema}\".\"{sequence_name}\"', 1, false)")
            )
