"""Datamart read replica access (README §10, Architecture §7.1).

A SEPARATE engine/pool from the metadata DB, connected with a READ-ONLY user.
Every connection is hardened at checkout:
  - session set READ ONLY
  - statement_timeout applied
  - default_transaction_read_only on

The datamart is physically per-tenant (`mint_{tenant_key}`) with schemas
core / mart / meta. We therefore resolve a `TenantContext` to a concrete
(database, search_path) scope. The Query Engine binds every query to that scope;
this module never builds query SQL itself.
"""

from __future__ import annotations

import re
from contextlib import contextmanager

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine, make_url

from app.core.config import settings
from app.core.logging import get_logger
from app.core.tenancy import TenantContext
from app.tenancy.subdomain import normalize_subdomain

log = get_logger(__name__)

# Cache one engine per resolved datamart database so pools are reused.
_engines: dict[str, Engine] = {}

# A tenant key is turned into a physical database name (mint_<key>) and is
# request-adjacent (it derives from the caller's tenant), so it is validated
# before interpolation: it must match the warehouse tenant_code shape and never
# name a non-tenant database. Mirrors meta.tenant's CHECK in the warehouse.
# HRIS JWT tenant_id is the host label (e.g. coca-cola from hris.coca-cola.lk);
# fold '-' / '.' to '_' so that key can be a Postgres identifier (mint_coca_cola).
_DATAMART_KEY_RE = re.compile(r"^[a-z][a-z0-9_]{0,57}$")
_RESERVED_KEYS = {"control", "default", "public", "postgres",
                  "template", "template0", "template1"}


def _safe_datamart_key(key: str) -> str:
    k = normalize_subdomain(key or "")
    if not _DATAMART_KEY_RE.match(k) or k in _RESERVED_KEYS:
        raise ValueError(f"unsafe datamart key: {key!r}")
    return k


def _harden(engine: Engine) -> None:
    """Force every checked-out connection into a strictly read-only posture.

    Applied as SESSION defaults at connect time, under autocommit so the
    connection is NOT left in an open transaction (psycopg3 forbids changing
    transaction characteristics mid-transaction). `default_transaction_read_only`
    makes every subsequent transaction read-only without us issuing per-query
    `SET TRANSACTION READ ONLY`.
    """

    @event.listens_for(engine, "connect")
    def _on_connect(dbapi_conn, _record):  # noqa: ANN001
        prev_autocommit = getattr(dbapi_conn, "autocommit", None)
        try:
            dbapi_conn.autocommit = True
        except Exception:  # pragma: no cover - drivers without autocommit attr
            prev_autocommit = None
        cur = dbapi_conn.cursor()
        try:
            cur.execute("SET default_transaction_read_only = on")
            cur.execute(f"SET statement_timeout = {int(settings.query_statement_timeout_ms)}")
            cur.execute("SET idle_in_transaction_session_timeout = 60000")
            # WS-4 — defense in depth: downgrade the whole session to a DB role that
            # is granted SELECT only on the semantic/mart schemas. Even if every
            # app-layer guard were bypassed, the database itself rejects writes/DDL
            # and reads of raw/staging tables. Off unless configured.
            role = settings.datamart_readonly_role.strip()
            if role:
                if not role.replace("_", "").isalnum():
                    raise ValueError(f"Invalid datamart_readonly_role: {role!r}")
                cur.execute(f'SET ROLE "{role}"')
        finally:
            cur.close()
            if prev_autocommit is not None:
                dbapi_conn.autocommit = prev_autocommit


def _datamart_url_for(datamart_key: str) -> str:
    """Build the DSN for a tenant's physical datamart database."""
    url = make_url(settings.datamart_ro_url)
    if settings.datamart_db_pattern:
        db_name = settings.datamart_db_pattern.format(tenant_key=_safe_datamart_key(datamart_key))
        url = url.set(database=db_name)
    return url.render_as_string(hide_password=False)


def get_datamart_engine(datamart_key: str) -> Engine:
    if datamart_key not in _engines:
        url = _datamart_url_for(datamart_key)
        engine = create_engine(
            url,
            pool_size=settings.datamart_pool_size,
            max_overflow=settings.datamart_pool_max_overflow,
            pool_pre_ping=True,
            future=True,
        )
        _harden(engine)
        _engines[datamart_key] = engine
        log.info("datamart_engine_created", datamart_key=datamart_key)
    return _engines[datamart_key]


@contextmanager
def datamart_connection(ctx: TenantContext, datamart_key: str):
    """Yield a read-only connection scoped to the tenant's schema search_path.

    `datamart_key` is resolved from the tenant record (Tenant.datamart_key). The
    search_path is pinned to the tenant's semantic + core schemas so unqualified
    table names can only resolve inside this tenant's data.
    """
    engine = get_datamart_engine(datamart_key)
    with engine.connect() as conn:
        # The session is already read-only (default_transaction_read_only=on set at
        # connect). Pin search_path to this tenant's schemas so unqualified names
        # can only resolve inside this tenant's data. SET is allowed in a read-only
        # transaction. search_path identifiers are validated from settings (not user
        # input) so they are interpolated, not bound (SET takes no bind params).
        # The catalogue is built entirely from the physical core schema (hr marts +
        # dims); no hr_semantic dependency. Pin search_path to core only.
        core = settings.datamart_schema_core
        if not core.replace("_", "").isalnum():
            raise ValueError("Invalid datamart schema name in settings")
        conn.execute(text(f'SET search_path TO "{core}"'))
        log.info(
            "datamart_query_scope",
            datamart_key=datamart_key,
            on_behalf=ctx.on_behalf,
        )
        yield conn
