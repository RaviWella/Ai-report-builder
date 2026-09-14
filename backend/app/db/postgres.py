"""Shared PostgreSQL connection pool (one database, many tenant schemas)."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, settings

_PG_TENANT_SCHEMA_KEY = "pg_tenant_schema"


def _set_public_search_path(dbapi_connection, _connection_record) -> None:  # noqa: ANN001
    cursor = dbapi_connection.cursor()
    cursor.execute("SET search_path TO public")
    cursor.close()


class PostgresDatabase:
    """One PostgreSQL database; tenant isolation via SET search_path."""

    def __init__(self, cfg: Settings | None = None) -> None:
        cfg = cfg or settings
        template_schema = cfg.pg_template_schema
        self._engine: Engine = create_engine(
            cfg.metadata_db_url,
            pool_pre_ping=True,
            pool_recycle=cfg.pg_pool_recycle_seconds,
            pool_size=cfg.pg_pool_size,
            max_overflow=cfg.pg_pool_max_overflow,
            pool_timeout=cfg.pg_pool_timeout_seconds,
            pool_use_lifo=True,
            connect_args={"options": f"-c search_path={template_schema}"},
            future=True,
        )
        event.listen(self._engine, "connect", _set_public_search_path)
        self._session_factory = sessionmaker(
            bind=self._engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
            future=True,
        )

        @event.listens_for(self._session_factory, "after_begin")
        def _apply_search_path(session, _transaction, connection) -> None:  # noqa: ANN001
            schema = session.info.get(_PG_TENANT_SCHEMA_KEY)
            if schema:
                connection.exec_driver_sql(f'SET search_path TO "{schema}", public')

    def session(self) -> Session:
        return self._session_factory()

    def pool_status(self) -> dict[str, int]:
        pool = self._engine.pool
        return {
            "size": pool.size(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "checked_in": pool.checkedin(),
        }

    def dispose(self) -> None:
        self._engine.dispose()


_postgres_db: PostgresDatabase | None = None


def init_postgres_database(cfg: Settings | None = None) -> PostgresDatabase:
    global _postgres_db
    _postgres_db = PostgresDatabase(cfg)
    return _postgres_db


def get_postgres_database() -> PostgresDatabase:
    if _postgres_db is None:
        return init_postgres_database()
    return _postgres_db


def get_platform_db() -> Generator[Session, None, None]:
    """FastAPI dependency — platform schema session (not tenant-scoped)."""
    postgres = get_postgres_database()
    session = postgres.session()
    try:
        session.execute(text("SET search_path TO platform, public"))
        yield session
    finally:
        session.close()
