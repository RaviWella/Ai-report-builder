"""Alembic migration environment — mirrors mint-analytics alembic/env.py."""
from __future__ import annotations

import os

from sqlalchemy import create_engine, text
from sqlalchemy import pool

from alembic import context

# Import models so their metadata is registered with Base.
from app.core.database import Base
from app.models import *  # noqa: F401, F403

config = context.config

# Logging config from alembic.ini
from logging.config import fileConfig
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url() -> str:
    """Synchronous URL for the application database (hrm_platform by default)."""
    try:
        from app.core.application_db import application_sync_url

        # DB provisioning runs in app lifespan (init_db); avoid duplicate admin
        # connections here — they can block startup when APP_AUTO_PROVISION=true.
        return application_sync_url()
    except Exception:
        url = os.environ.get("DATABASE_URL") or config.get_main_option("sqlalchemy.url")
        if url and "+asyncpg" in url:
            url = url.replace("+asyncpg", "+psycopg2")
        elif url and url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
        return url or ""


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (no live DB connection)."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # Include hrm_control schema in autogenerate scope
        include_schemas=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    url = get_url()
    connectable = create_engine(url, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        # Ensure hrm_control schema exists before running migrations
        connection.execute(text("CREATE SCHEMA IF NOT EXISTS hrm_control"))
        connection.commit()

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # Include hrm_control schema in autogenerate scope
            include_schemas=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
