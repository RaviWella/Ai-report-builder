"""Alembic environment — multi-tenant PostgreSQL (schema-per-tenant pattern).

Phase 1: public template + platform registry (public.alembic_version)
Phase 2: each tenant schema (public.alembic_version__{schema})
"""

from __future__ import annotations

import logging
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool, text

from app.core.config import settings
from app.db.pg_tenant_db import is_tenant_schema, list_tenant_schemas
from app.db.metadata import PostgresBase
from app.db.platform_models import PlatformBase

config = context.config
logger = logging.getLogger("alembic.multi_tenant")

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = [PostgresBase.metadata, PlatformBase.metadata]

MANAGED_SCHEMAS = {None, "public", "platform"}


def include_name(name, type_, parent_names):  # noqa: ANN001
    if type_ == "schema":
        return name in MANAGED_SCHEMAS
    return True


def include_object(object_, name, type_, reflected, compare_to):  # noqa: ANN001
    if type_ == "table":
        if name == "alembic_version" or name.startswith("alembic_version__"):
            return False
        return getattr(object_, "schema", None) in (None, "public", "platform")
    return True


def _run_migrations_for_schema(connection, schema: str) -> None:
    if schema == "public":
        connection.execute(text("SET search_path TO public, platform"))
        version_table = "alembic_version"
        version_table_schema = "public"
    else:
        connection.execute(text(f'SET search_path TO "{schema}", public'))
        version_table = f"alembic_version__{schema}"
        version_table_schema = "public"
    connection.commit()

    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_schemas=True,
        include_name=include_name,
        include_object=include_object,
        version_table=version_table,
        version_table_schema=version_table_schema,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_offline() -> None:
    context.configure(
        url=settings.metadata_db_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        include_name=include_name,
        include_object=include_object,
        version_table_schema="public",
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section, {}) or {}
    configuration["sqlalchemy.url"] = settings.metadata_db_url
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        logger.info("--- Phase 1: migrating public + platform schemas ---")
        _run_migrations_for_schema(connection, "public")

        tenant_schemas = list_tenant_schemas(connection)
        if not tenant_schemas:
            logger.info("No tenant schemas found; skipping phase 2.")
            return

        logger.info(
            "Phase 2: migrating %d tenant schema(s): %s",
            len(tenant_schemas),
            ", ".join(tenant_schemas),
        )

        from alembic.script import ScriptDirectory

        script = ScriptDirectory.from_config(config)
        head_rev = script.get_current_head()
        failed: list[tuple[str, str]] = []

        for schema in tenant_schemas:
            if not is_tenant_schema(schema):
                continue
            logger.info("--- Migrating tenant schema: %s ---", schema)
            try:
                _run_migrations_for_schema(connection, schema)
                logger.info("--- Successfully migrated: %s ---", schema)
            except Exception as exc:
                err_msg = str(exc)
                connection.rollback()
                connection.execute(text("SET search_path TO public"))
                connection.commit()

                if "Can't locate revision" in err_msg and head_rev:
                    vt = f"alembic_version__{schema}"
                    logger.warning(
                        "Tenant %s has stale revision; stamping at HEAD %s",
                        schema,
                        head_rev,
                    )
                    connection.execute(
                        text(f'UPDATE public."{vt}" SET version_num = :rev'),
                        {"rev": head_rev},
                    )
                    connection.commit()
                else:
                    logger.error("FAILED tenant schema %s: %s", schema, exc)
                    failed.append((schema, err_msg))

        if failed:
            summary = "; ".join(f"{s}: {e[:100]}" for s, e in failed)
            raise RuntimeError(
                f"Migration failed for {len(failed)} tenant(s): {summary}"
            )


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
