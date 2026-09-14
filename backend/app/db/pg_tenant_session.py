"""Open PostgreSQL sessions scoped to a tenant schema."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from collections.abc import Generator

from fastapi import HTTPException
from sqlalchemy import event, text
from sqlalchemy.exc import TimeoutError as SATimeoutError
from sqlalchemy.orm import Session

from app.core.config import Settings, settings
from app.core.exceptions import PostgresSchemaError, TenantError, TenantNotProvisionedError
from app.db.pg_schema_provisioner import PostgresSchemaProvisioner
from app.db.pg_tenant_db import restore_search_path
from app.db.postgres import PostgresDatabase, get_postgres_database
from app.repositories.tenant_provision import (
    ensure_tenant_provision_record,
    get_provision_status,
    is_tenant_provisioned,
)
from app.tenancy.pg_schema import subdomain_to_pg_schema

logger = logging.getLogger(__name__)

_PG_TENANT_SCHEMA_KEY = "pg_tenant_schema"
_SEARCH_PATH_HOOKS_REGISTERED = False


def tenant_schema_from_session(session: Session) -> str | None:
    schema = session.info.get(_PG_TENANT_SCHEMA_KEY)
    return str(schema) if schema else None


def apply_tenant_search_path(session: Session) -> None:
    schema = tenant_schema_from_session(session)
    if schema:
        restore_search_path(session, schema)


def commit_tenant_session(session: Session) -> None:
    session.commit()
    apply_tenant_search_path(session)


def _register_tenant_search_path_hooks() -> None:
    global _SEARCH_PATH_HOOKS_REGISTERED
    if _SEARCH_PATH_HOOKS_REGISTERED:
        return
    _SEARCH_PATH_HOOKS_REGISTERED = True

    @event.listens_for(Session, "after_begin")
    def _restore_search_path_after_begin(session, _transaction, connection) -> None:  # noqa: ANN001
        schema = session.info.get(_PG_TENANT_SCHEMA_KEY)
        if schema:
            connection.execute(text(f'SET search_path TO "{schema}", public'))


class PostgresTenantSessionManager:
    """Open PostgreSQL sessions scoped to a tenant subdomain schema."""

    def __init__(self, cfg: Settings | None = None, postgres: PostgresDatabase | None = None) -> None:
        self._settings = cfg or settings
        self._postgres = postgres or get_postgres_database()
        self._provisioner = PostgresSchemaProvisioner(self._settings)

    def _log_pool_exhausted(self, session: Session, schema_name: str, subdomain: str) -> None:
        # WARNING, not logger.exception: this is retryable, not a bug (matches
        # main.py's SATimeoutError handler's own framing) — a full ERROR-level
        # stack trace on every occurrence is needless cost precisely when the
        # system is already under the load this is meant to handle gracefully.
        session.rollback()
        logger.warning(
            "PostgreSQL connection pool exhausted",
            extra={
                "schema": schema_name,
                "subdomain": subdomain,
                "pool": self._postgres.pool_status(),
            },
        )

    def _validate_tenant_for_provisioning(self, subdomain: str, platform_session: Session) -> None:
        if self._settings.pg_allow_unregistered_tenants and self._settings.environment in (
            "local",
            "development",
            "staging",
        ):
            return

        if is_tenant_provisioned(platform_session, subdomain):
            return

        row = get_provision_status(platform_session, subdomain)
        if row is not None and row.status != "active":
            raise TenantNotProvisionedError(subdomain)

        schema_name = subdomain_to_pg_schema(subdomain)
        if ensure_tenant_provision_record(
            platform_session,
            subdomain,
            schema_name,
            provisioned_by="lazy_provision",
        ):
            platform_session.commit()
            logger.info(
                "Auto-provisioned tenant on first access",
                extra={"subdomain": subdomain, "schema": schema_name},
            )

    def ensure_tenant_schema(self, subdomain: str) -> bool:
        _register_tenant_search_path_hooks()
        schema_name = subdomain_to_pg_schema(subdomain)
        session = self._postgres.session()
        session.info[_PG_TENANT_SCHEMA_KEY] = schema_name
        try:
            created = self._provisioner.ensure_schema(session, schema_name)
            session.execute(text(f'SET search_path TO "{schema_name}", public'))
            session.commit()
            restore_search_path(session, schema_name)
            if created:
                logger.info("Tenant PostgreSQL schema ready", extra={"schema": schema_name})
            return created
        except TenantError:
            session.rollback()
            raise
        except SATimeoutError:
            self._log_pool_exhausted(session, schema_name, subdomain)
            raise
        except Exception as exc:
            session.rollback()
            logger.exception(
                "PostgreSQL tenant provisioning failed",
                extra={"schema": schema_name, "subdomain": subdomain},
            )
            raise PostgresSchemaError(str(exc)) from exc
        finally:
            session.close()

    @contextmanager
    def scope(self, subdomain: str) -> Generator[Session, None, None]:
        _register_tenant_search_path_hooks()
        schema_name = subdomain_to_pg_schema(subdomain)
        session = self._postgres.session()
        try:
            # Platform checks first, before binding the tenant search_path hook,
            # so one connection covers registry lookup + tenant work. Holding a
            # second session for the whole request exhausted the QueuePool (5+5)
            # under concurrent FastAPI threadpool requests.
            session.execute(text("SET search_path TO platform, public"))
            self._validate_tenant_for_provisioning(subdomain, session)
            session.info[_PG_TENANT_SCHEMA_KEY] = schema_name
            created = self._provisioner.ensure_schema(session, schema_name)
            session.execute(text(f'SET search_path TO "{schema_name}", public'))
            yield session
            session.commit()
            restore_search_path(session, schema_name)
            if created:
                logger.info("Tenant PostgreSQL schema ready", extra={"schema": schema_name})
        except (TenantError, HTTPException):
            # HTTPException is how endpoints report a deliberate 4xx/5xx (bad
            # input, a downstream service failure, ...) — it must reach FastAPI
            # unchanged, not get relabelled as a schema/provisioning failure and
            # fall through to a generic unhandled 500.
            session.rollback()
            raise
        except SATimeoutError:
            self._log_pool_exhausted(session, schema_name, subdomain)
            raise
        except Exception as exc:
            session.rollback()
            logger.exception(
                "PostgreSQL tenant operation failed",
                extra={"schema": schema_name, "subdomain": subdomain},
            )
            raise PostgresSchemaError(str(exc)) from exc
        finally:
            session.close()


_postgres_tenant_session_manager: PostgresTenantSessionManager | None = None


def init_postgres_tenant_session_manager(
    cfg: Settings | None = None,
) -> PostgresTenantSessionManager:
    global _postgres_tenant_session_manager
    _postgres_tenant_session_manager = PostgresTenantSessionManager(cfg)
    return _postgres_tenant_session_manager


def get_postgres_tenant_session_manager() -> PostgresTenantSessionManager:
    if _postgres_tenant_session_manager is None:
        return init_postgres_tenant_session_manager()
    return _postgres_tenant_session_manager


@contextmanager
def worker_pg_session(subdomain: str) -> Generator[Session, None, None]:
    """Worker-safe tenant-scoped session (mirrors API scope)."""
    with get_postgres_tenant_session_manager().scope(subdomain) as session:
        yield session
