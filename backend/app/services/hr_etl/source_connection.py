"""Dynamic ETL source connections (MySQL or PostgreSQL).

Tenant registry stores connection fields in legacy ``mysql_*`` columns; they
apply to whichever ``source_type`` is configured for that tenant.
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Iterator, Literal
from urllib.parse import quote_plus

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.core.config import settings

logger = logging.getLogger("hr_etl.source")

SourceType = Literal["mysql", "postgres"]
SUPPORTED_SOURCE_TYPES: tuple[SourceType, ...] = ("mysql", "postgres")

_current_dialect: ContextVar[SourceType] = ContextVar(
    "etl_source_dialect", default="mysql"
)


@dataclass(frozen=True)
class TenantSourceConfig:
    tenant_id: str
    source_type: SourceType
    host: str
    port: int
    database: str
    user: str
    password: str
    # SSH tunnel fields — only populated when source_connection_id is used
    ssh_enabled: bool = False
    ssh_host: str | None = None
    ssh_port: int | None = None
    ssh_username: str | None = None
    ssh_auth_method: str | None = None
    ssh_private_key: str | None = None
    ssh_password: str | None = None
    ssh_key_passphrase: str | None = None

    @property
    def default_port(self) -> int:
        return 5432 if self.source_type == "postgres" else 3306


def normalize_source_type(value: str | None) -> SourceType:
    raw = (value or "mysql").strip().lower()
    if raw in ("postgresql", "pg", "postgres"):
        return "postgres"
    if raw in ("mysql", "mariadb"):
        return "mysql"
    raise ValueError(
        f"Unsupported source_type '{value}'. Use one of: {', '.join(SUPPORTED_SOURCE_TYPES)}"
    )


def get_dialect() -> SourceType:
    return _current_dialect.get()


@contextmanager
def source_dialect(dialect: SourceType) -> Iterator[None]:
    """Set active SQL dialect for extractor SQL builders within this block."""
    token = _current_dialect.set(dialect)
    try:
        yield
    finally:
        _current_dialect.reset(token)


def qident(name: str) -> str:
    """Quote an identifier (reserved words like ``date``)."""
    if get_dialect() == "postgres":
        return f'"{name}"'
    return f"`{name}`"


# Re-export dialect SQL builders (implementation in sql_dialect.py)
from app.services.hr_etl.sql_dialect import (  # noqa: E402
    sql_concat,
    sql_lpad,
    sql_minute_diff,
    sql_now,
    sql_timestamp_from_date_and_time,
)


def _decrypt_password(encrypted: str) -> str:
    if not settings.DB_ENCRYPTION_KEY:
        return encrypted
    from cryptography.fernet import Fernet

    f = Fernet(settings.DB_ENCRYPTION_KEY.encode())
    return f.decrypt(encrypted.encode()).decode()


def _registry_select_sql(*, with_source_type: bool) -> str:
    st_col = (
        "COALESCE(source_type, 'mysql') AS source_type"
        if with_source_type
        else "'mysql' AS source_type"
    )
    return f"""
        SELECT
            tenant_id,
            {st_col},
            mysql_host AS host,
            mysql_port AS port,
            mysql_db AS database,
            mysql_user AS user,
            mysql_password_enc AS password_enc,
            source_connection_id
        FROM hrm_control.tenant_registry
        WHERE tenant_id = :tid
    """


def config_from_etl_source_row(row: object) -> TenantSourceConfig:
    """Build ETL config from hrm_control.tenant_etl_sources inline credentials."""
    from app.services.tenant_etl_sources import TenantEtlSourceRow

    if not isinstance(row, TenantEtlSourceRow):
        raise TypeError("row must be TenantEtlSourceRow")
    if not row.has_control_plane_credentials():
        raise ValueError(
            f"ETL source id={row.id} has no credentials on tenant_etl_sources"
        )
    st = normalize_source_type(row.source_type)
    port = row.port
    if port is None:
        port = 5432 if st == "postgres" else 3306
    return TenantSourceConfig(
        tenant_id=row.tenant_id,
        source_type=st,
        host=str(row.host),
        port=int(port),
        database=str(row.database_name),
        user=str(row.username),
        password=_decrypt_password(str(row.password_encrypted)),
    )


def _load_from_database_connection(
    pg: Engine,
    connection_id: int,
    tenant_id: str,
    *,
    mart_schema: str | None = None,
) -> TenantSourceConfig:
    """Load a TenantSourceConfig from a saved DatabaseConnection record."""
    if mart_schema:
        from_table = f'"{mart_schema}".database_connections'
    else:
        from_table = "database_connections"

    row = None
    with pg.connect() as conn:
        row = conn.execute(
            text(
                f"""
                SELECT engine, host, port, database_name, username, password_encrypted,
                       ssh_enabled, ssh_host, ssh_port, ssh_username, ssh_auth_method,
                       ssh_private_key_encrypted, ssh_password_encrypted,
                       ssh_key_passphrase_encrypted
                FROM {from_table}
                WHERE id = :cid AND is_active = TRUE
                """
            ),
            {"cid": connection_id},
        ).mappings().first()

    if not row:
        raise LookupError(
            f"DatabaseConnection id={connection_id} not found or inactive "
            f"(referenced by tenant '{tenant_id}')"
        )

    engine_val = (row["engine"] or "mysql").lower()
    source_type = normalize_source_type(engine_val)
    password = _decrypt_password(row["password_encrypted"])

    # SSH tunnel: build a temporary engine via the SSH tunnel helper if needed
    if row.get("ssh_enabled"):
        logger.info(
            "source_connection id=%s uses SSH tunnel — tunnel will be opened by build_source_engine",
            connection_id,
        )

    return TenantSourceConfig(
        tenant_id=tenant_id,
        source_type=source_type,
        host=row["host"],
        port=int(row["port"]),
        database=row["database_name"],
        user=row["username"],
        password=password,
        # Carry SSH fields so build_source_engine can open a tunnel if needed
        ssh_enabled=bool(row.get("ssh_enabled", False)),
        ssh_host=row.get("ssh_host"),
        ssh_port=row.get("ssh_port"),
        ssh_username=row.get("ssh_username"),
        ssh_auth_method=row.get("ssh_auth_method"),
        ssh_private_key=_decrypt_password(row["ssh_private_key_encrypted"])
            if row.get("ssh_private_key_encrypted") else None,
        ssh_password=_decrypt_password(row["ssh_password_encrypted"])
            if row.get("ssh_password_encrypted") else None,
        ssh_key_passphrase=_decrypt_password(row["ssh_key_passphrase_encrypted"])
            if row.get("ssh_key_passphrase_encrypted") else None,
    )


def load_tenant_source(
    pg: Engine,
    tenant_id: str,
    *,
    mart_pg: Engine | None = None,
    mart_schema: str | None = None,
) -> "TenantSourceConfig":
    """Load source config; registry on ``pg`` (platform), connections on warehouse mart."""
    with pg.connect() as conn:
        try:
            row = conn.execute(
                text(_registry_select_sql(with_source_type=True)),
                {"tid": tenant_id},
            ).mappings().first()
        except Exception as exc:
            if "source_type" not in str(exc).lower() and "source_connection_id" not in str(exc).lower():
                raise
            logger.warning(
                "tenant_registry column missing; retrying without new columns. "
                "Run alembic upgrade head."
            )
            row = conn.execute(
                text(_registry_select_sql(with_source_type=False).replace(
                    ",\n            source_connection_id", ""
                )),
                {"tid": tenant_id},
            ).mappings().first()

    if not row:
        raise LookupError(f"Tenant '{tenant_id}' not found in tenant_registry")

    # ── Dynamic connection path ──────────────────────────────────────
    source_connection_id = row.get("source_connection_id")
    if source_connection_id:
        logger.info(
            "tenant=%s using dynamic source_connection_id=%s",
            tenant_id, source_connection_id,
        )
        conn_pg = mart_pg or pg
        if mart_schema is None:
            from app.core.warehouse import get_layout_sync

            mart_schema = get_layout_sync(tenant_id).mart_schema
        return _load_from_database_connection(
            conn_pg, int(source_connection_id), tenant_id, mart_schema=mart_schema
        )

    # ── Legacy inline-fields path ────────────────────────────────────
    source_type = normalize_source_type(row["source_type"])
    port = row["port"]
    if port is None:
        port = 5432 if source_type == "postgres" else 3306

    return TenantSourceConfig(
        tenant_id=tenant_id,
        source_type=source_type,
        host=row["host"],
        port=int(port),
        database=row["database"],
        user=row["user"],
        password=_decrypt_password(row["password_enc"]),
    )


def _encrypt_for_tunnel(plain: str) -> str:
    """Encrypt a plaintext credential for use with the tunnel helper."""
    from cryptography.fernet import Fernet
    key = settings.DB_ENCRYPTION_KEY
    if not key:
        raise ValueError("DB_ENCRYPTION_KEY is not set")
    return Fernet(key.encode() if isinstance(key, str) else key).encrypt(plain.encode()).decode()


def build_source_engine(config: TenantSourceConfig) -> Engine:
    """Build a sync SQLAlchemy engine for the ETL source.

    When config.ssh_enabled is True (dynamic connection path), opens an SSH
    tunnel via the database_connection service's tunnel manager and routes
    the connection through the local forwarded port.
    """
    host = config.host
    port = config.port

    # ── SSH tunnel (dynamic connection path only) ────────────────────
    if config.ssh_enabled:
        from app.models.database_connection import DatabaseConnection
        from app.services.database_connection import _open_tunnel, _tunnel_pool, _tunnel_pool_lock

        # Build a minimal DatabaseConnection-like object for the tunnel helper
        temp_conn = DatabaseConnection(
            id=-2,  # sentinel — not persisted
            name=f"etl-source-{config.tenant_id}",
            engine=config.source_type,
            host=config.host,
            port=config.port,
            database_name=config.database,
            username=config.user,
            password_encrypted="",  # not used by tunnel helper
            ssh_enabled=True,
            ssh_host=config.ssh_host,
            ssh_port=config.ssh_port or 22,
            ssh_username=config.ssh_username,
            ssh_auth_method=config.ssh_auth_method or "key",
            ssh_private_key_encrypted=(
                _encrypt_for_tunnel(config.ssh_private_key) if config.ssh_private_key else None
            ),
            ssh_password_encrypted=(
                _encrypt_for_tunnel(config.ssh_password) if config.ssh_password else None
            ),
            ssh_key_passphrase_encrypted=(
                _encrypt_for_tunnel(config.ssh_key_passphrase) if config.ssh_key_passphrase else None
            ),
        )
        tunnel = _open_tunnel(temp_conn)
        # Store in tunnel pool keyed by a negative sentinel so it can be cleaned up
        with _tunnel_pool_lock:
            _tunnel_pool[-2] = tunnel
        host = "127.0.0.1"
        port = tunnel.local_port
        logger.info(
            "ETL source SSH tunnel opened for tenant=%s: local port %s",
            config.tenant_id, port,
        )

    user_q = quote_plus(config.user, safe="")
    pass_q = quote_plus(config.password, safe="")
    db_q = quote_plus(config.database, safe="")

    if config.source_type == "postgres":
        url = (
            f"postgresql+psycopg2://{user_q}:{pass_q}"
            f"@{host}:{port}/{db_q}"
        )
    else:
        url = (
            f"mysql+pymysql://{user_q}:{pass_q}"
            f"@{host}:{port}/{db_q}"
        )

    logger.info(
        "source engine tenant=%s type=%s host=%s:%s db=%s",
        config.tenant_id,
        config.source_type,
        host,
        port,
        config.database,
    )

    engine_kwargs: dict = {"pool_pre_ping": True, "pool_recycle": 1800}
    if config.source_type == "mysql":
        session_init = (settings.ETL_MYSQL_SESSION_INIT or "").strip()
        connect_args: dict = {
            "connect_timeout": settings.ETL_MYSQL_CONNECT_TIMEOUT_SEC,
            "read_timeout": settings.ETL_MYSQL_READ_TIMEOUT_SEC,
            "write_timeout": settings.ETL_MYSQL_WRITE_TIMEOUT_SEC,
        }
        if session_init:
            connect_args["init_command"] = session_init
        engine_kwargs["connect_args"] = connect_args

    return create_engine(url, **engine_kwargs)


def get_source_engine(tenant_id: str, *, pg: Engine | None = None) -> tuple[Engine, SourceType]:
    """Load tenant source config from registry and return (engine, dialect)."""
    from app.core.warehouse import (
        get_layout_sync,
        get_platform_engine_sync,
        get_warehouse_engine_sync,
    )

    platform = pg or get_platform_engine_sync()
    warehouse = get_warehouse_engine_sync(tenant_id, provision=False)
    layout = get_layout_sync(tenant_id)
    config = load_tenant_source(
        platform,
        tenant_id,
        mart_pg=warehouse,
        mart_schema=layout.mart_schema,
    )
    return build_source_engine(config), config.source_type
