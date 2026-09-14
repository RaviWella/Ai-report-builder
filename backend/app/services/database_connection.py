"""Database Connection Service for MintHRM.

Ported from mint-analytics. Lets HR analysts connect to any customer database
(MySQL, PostgreSQL, SQL Server) to run ad-hoc queries and build visualizations.

Provides:
  - SQL safety validation (SELECT-only, no file I/O, no system schemas)
  - Fernet encryption/decryption for stored credentials
  - LRU-bounded engine pool with SSH tunnel support
  - DatabaseConnectionService  — CRUD + test + health
  - QueryEngine                — safe SELECT execution with RLS
  - SchemaInspector            — schema/table/field discovery
"""
from __future__ import annotations

import logging
import os
import re
import shutil
import socket
import subprocess
import tempfile
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import sqlparse
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import create_engine, event as sa_event, inspect as sa_inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.database_connection import DatabaseConnection

logger = logging.getLogger("database_connection")


# ── SQL Safety Validation ────────────────────────────────────────

_FORBIDDEN_LEADING = {
    "DELETE", "UPDATE", "INSERT", "MERGE",
    "DROP", "TRUNCATE", "ALTER", "CREATE", "RENAME",
    "GRANT", "REVOKE",
    "COPY", "LOAD", "UNLOAD",
    "EXEC", "EXECUTE", "CALL",
    "BEGIN", "COMMIT", "ROLLBACK", "SAVEPOINT",
    "VACUUM", "ANALYZE", "EXPLAIN",
    "SET", "RESET",
    "LOCK", "UNLOCK",
}

_FORBIDDEN_ANYWHERE = re.compile(
    r"\b("
    r"INTO\s+OUTFILE|INTO\s+DUMPFILE|"
    r"LOAD_FILE\s*\(|"
    r"pg_read_file|pg_ls_dir|"
    r"COPY\s+\w+\s+(?:FROM|TO)"
    r")",
    re.IGNORECASE,
)

_FORBIDDEN_SCHEMAS = re.compile(
    r"\b(?:FROM|JOIN|UPDATE|INTO)\s+"
    r"(?:pg_catalog|pg_toast|mysql\.user|performance_schema|sys\.|dba_users)\b",
    re.IGNORECASE,
)

_COMMENT_LINE  = re.compile(r"--[^\n]*")
_COMMENT_BLOCK = re.compile(r"/\*.*?\*/", re.DOTALL)


class SQLSafetyError(Exception):
    """Raised when a SQL query fails safety validation."""


def _first_keyword(statement) -> str:
    for token in statement.tokens:
        if token.is_whitespace or token.ttype in (
            sqlparse.tokens.Comment,
            sqlparse.tokens.Comment.Single,
            sqlparse.tokens.Comment.Multiline,
        ):
            continue
        val = token.value.strip()
        if not val or val in ("(", ")", ";", ","):
            continue
        return val.upper().split()[0] if val else ""
    return ""


def validate_sql_safe(sql: str) -> str:
    """Validate that SQL is read-only and safe to execute.

    Returns cleaned SQL on success; raises SQLSafetyError on failure.
    """
    if not sql or not isinstance(sql, str):
        raise SQLSafetyError("SQL query is empty or invalid")

    cleaned = _COMMENT_BLOCK.sub(" ", sql)
    cleaned = _COMMENT_LINE.sub(" ", cleaned)
    cleaned = cleaned.strip().rstrip(";").strip()

    if not cleaned:
        raise SQLSafetyError("SQL query is empty after stripping comments")

    parsed = sqlparse.parse(cleaned)
    real_statements = [s for s in parsed if s.tokens and str(s).strip()]
    if len(real_statements) != 1:
        raise SQLSafetyError(
            f"Only one statement allowed per query (got {len(real_statements)})"
        )

    first_kw = _first_keyword(real_statements[0])
    if first_kw not in ("SELECT", "WITH"):
        if first_kw in _FORBIDDEN_LEADING:
            raise SQLSafetyError(f"Statement type not allowed: {first_kw}")
        raise SQLSafetyError(f"Only SELECT statements allowed (got '{first_kw}')")

    match = _FORBIDDEN_ANYWHERE.search(cleaned)
    if match:
        raise SQLSafetyError(f"Forbidden SQL pattern: {match.group(0)}")

    match = _FORBIDDEN_SCHEMAS.search(cleaned)
    if match:
        raise SQLSafetyError(f"Forbidden system schema access: {match.group(0)}")

    return cleaned


# ── Encryption ───────────────────────────────────────────────────

def _get_fernet() -> Fernet:
    key = settings.DB_ENCRYPTION_KEY
    if not key:
        raise ValueError(
            "DB_ENCRYPTION_KEY is not set. Generate one with: "
            'python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
        )
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_password(plain: str) -> str:
    return _get_fernet().encrypt(plain.encode()).decode()


def decrypt_password(encrypted: str) -> str:
    try:
        return _get_fernet().decrypt(encrypted.encode()).decode()
    except InvalidToken:
        raise ValueError("Failed to decrypt password — DB_ENCRYPTION_KEY may have changed")


# ── Connection String Builder ────────────────────────────────────

def build_connection_string(
    conn: DatabaseConnection,
    *,
    use_async: bool = False,
    host_override: Optional[str] = None,
    port_override: Optional[int] = None,
) -> str:
    """Build a SQLAlchemy URL from a DatabaseConnection record.

    host_override / port_override let the SSH-tunnel path swap in the local
    127.0.0.1:<ephemeral> address while keeping all other details.
    """
    password = decrypt_password(conn.password_encrypted)
    engine   = conn.engine.lower()
    host     = host_override if host_override is not None else conn.host
    port     = port_override if port_override is not None else conn.port
    db       = conn.database_name
    user     = conn.username

    if engine == "postgres":
        driver = "postgresql+psycopg2"
        url = f"{driver}://{user}:{password}@{host}:{port}/{db}"
    elif engine == "mysql":
        driver = "mysql+aiomysql" if use_async else "mysql+pymysql"
        url = f"{driver}://{user}:{password}@{host}:{port}/{db}"
    elif engine == "sqlserver":
        url = (
            f"mssql+pyodbc://{user}:{password}@{host}:{port}/{db}"
            "?driver=ODBC+Driver+17+for+SQL+Server"
        )
    else:
        raise ValueError(f"Unsupported engine: {engine}")

    if conn.ssl_mode and engine in ("postgres", "mysql"):
        sep = "?" if "?" not in url else "&"
        url += f"{sep}sslmode={conn.ssl_mode}"

    return url


# ── Engine Pool (LRU-bounded) ────────────────────────────────────

MAX_ENGINES              = 100
ENGINE_POOL_SIZE         = 2
ENGINE_MAX_OVERFLOW      = 3
QUERY_STATEMENT_TIMEOUT_MS = 30_000   # 30 s

_engine_pool: OrderedDict[int, Engine] = OrderedDict()
_engine_pool_lock = threading.RLock()


def _install_connect_handlers(
    engine: Engine, dialect: str, default_schema: Optional[str]
) -> None:
    """Install per-connection statement timeout and default schema."""
    if dialect == "postgres":
        @sa_event.listens_for(engine, "connect")
        def _pg_setup(dbapi_conn, _rec):
            with dbapi_conn.cursor() as cur:
                cur.execute(f"SET statement_timeout = {QUERY_STATEMENT_TIMEOUT_MS}")
                if default_schema:
                    cur.execute(f'SET search_path TO "{default_schema}", public')
    elif dialect == "mysql":
        @sa_event.listens_for(engine, "connect")
        def _mysql_setup(dbapi_conn, _rec):
            with dbapi_conn.cursor() as cur:
                cur.execute(
                    f"SET SESSION MAX_EXECUTION_TIME = {QUERY_STATEMENT_TIMEOUT_MS}"
                )
                if default_schema:
                    cur.execute(f"USE `{default_schema}`")


# ── SSH Tunnel Manager ───────────────────────────────────────────
#
# Uses the system OpenSSH client (subprocess) instead of paramiko/sshtunnel.
# Tunnels are paired with engines; eviction always disposes the engine FIRST
# then kills the tunnel to avoid deadlocks.

@dataclass
class _Tunnel:
    proc: subprocess.Popen
    local_port: int
    key_path: Optional[str] = None


_tunnel_pool: dict[int, _Tunnel] = {}
_tunnel_pool_lock = threading.RLock()


def _pick_local_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _wait_for_port(port: int, timeout: float = 10.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.1)
    return False


def _open_tunnel(conn: DatabaseConnection) -> _Tunnel:
    if not conn.ssh_host or not conn.ssh_username:
        raise ValueError("SSH tunnel requires ssh_host and ssh_username")
    if shutil.which("ssh") is None:
        raise RuntimeError(
            "OpenSSH client not installed. Add `openssh-client` to the Dockerfile."
        )

    auth = (conn.ssh_auth_method or "key").lower()
    key_path: Optional[str] = None

    base_args = [
        "ssh", "-N", "-T",
        "-o", "ExitOnForwardFailure=yes",
        "-o", "ServerAliveInterval=30",
        "-o", "ServerAliveCountMax=3",
        "-o", "ConnectTimeout=15",
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        "-o", "LogLevel=ERROR",
        "-o", "BatchMode=yes",
    ]

    if auth == "key":
        if not conn.ssh_private_key_encrypted:
            raise ValueError("SSH key auth requested but ssh_private_key is empty")
        pem = decrypt_password(conn.ssh_private_key_encrypted)
        fd, key_path = tempfile.mkstemp(prefix="mint_ssh_", suffix=".pem")
        try:
            os.write(fd, pem.encode())
        finally:
            os.close(fd)
        os.chmod(key_path, 0o600)
        base_args += ["-i", key_path, "-o", "IdentitiesOnly=yes"]
    elif auth == "password":
        raise ValueError(
            "SSH password authentication is not supported in v1. Use a private key."
        )
    else:
        raise ValueError(f"Unsupported ssh_auth_method: {auth}")

    local_port = _pick_local_port()
    cmd = base_args + [
        "-L", f"127.0.0.1:{local_port}:{conn.host}:{conn.port}",
        "-p", str(conn.ssh_port or 22),
        f"{conn.ssh_username}@{conn.ssh_host}",
    ]

    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=os.environ.copy(),
    )

    if not _wait_for_port(local_port, timeout=15.0):
        try:
            proc.terminate()
            _, err = proc.communicate(timeout=2)
        except Exception:
            err = b""
        if key_path:
            try:
                os.unlink(key_path)
            except Exception:
                pass
        raise RuntimeError(
            f"SSH tunnel failed to come up within 15s. stderr: "
            f"{err.decode(errors='replace').strip() or '(empty)'}"
        )

    logger.info(
        "[TunnelManager] Opened tunnel for connection %s: %s@%s:%s -> %s:%s "
        "(local 127.0.0.1:%s, pid %s)",
        conn.id, conn.ssh_username, conn.ssh_host, conn.ssh_port or 22,
        conn.host, conn.port, local_port, proc.pid,
    )
    return _Tunnel(proc=proc, local_port=local_port, key_path=key_path)


def _close_tunnel(connection_id: int) -> None:
    with _tunnel_pool_lock:
        tunnel = _tunnel_pool.pop(connection_id, None)
    if tunnel is None:
        return
    try:
        tunnel.proc.terminate()
        try:
            tunnel.proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            tunnel.proc.kill()
            tunnel.proc.wait(timeout=2)
        logger.info("[TunnelManager] Closed tunnel for connection %s", connection_id)
    except Exception as exc:
        logger.warning("[TunnelManager] Failed to stop tunnel %s: %s", connection_id, exc)
    finally:
        if tunnel.key_path:
            try:
                os.unlink(tunnel.key_path)
            except Exception:
                pass


def _get_engine(conn: DatabaseConnection) -> Engine:
    """Get or create a sync SQLAlchemy engine (LRU-bounded, SSH-aware)."""
    with _engine_pool_lock:
        if conn.id in _engine_pool:
            if conn.ssh_enabled:
                with _tunnel_pool_lock:
                    tunnel = _tunnel_pool.get(conn.id)
                if tunnel and tunnel.proc.poll() is not None:
                    logger.warning(
                        "[TunnelManager] Tunnel for connection %s died (exit %s), rebuilding",
                        conn.id, tunnel.proc.returncode,
                    )
                    stale = _engine_pool.pop(conn.id, None)
                    if stale:
                        try:
                            stale.dispose()
                        except Exception:
                            pass
                    _close_tunnel(conn.id)
                    # fall through to rebuild
                else:
                    _engine_pool.move_to_end(conn.id)
                    return _engine_pool[conn.id]
            else:
                _engine_pool.move_to_end(conn.id)
                return _engine_pool[conn.id]

        host_override = port_override = None
        if conn.ssh_enabled:
            with _tunnel_pool_lock:
                tunnel = _tunnel_pool.get(conn.id)
                if tunnel is None:
                    tunnel = _open_tunnel(conn)
                    _tunnel_pool[conn.id] = tunnel
            host_override = "127.0.0.1"
            port_override = tunnel.local_port

        url = build_connection_string(
            conn, use_async=False,
            host_override=host_override, port_override=port_override,
        )
        engine = create_engine(
            url,
            pool_size=ENGINE_POOL_SIZE,
            max_overflow=ENGINE_MAX_OVERFLOW,
            pool_timeout=15,
            pool_recycle=1800,
            pool_pre_ping=True,
        )
        _install_connect_handlers(engine, conn.engine.lower(), conn.default_schema)

        _engine_pool[conn.id] = engine
        _engine_pool.move_to_end(conn.id)

        # Evict LRU if over capacity — dispose engine BEFORE closing tunnel
        while len(_engine_pool) > MAX_ENGINES:
            evicted_id, evicted_engine = _engine_pool.popitem(last=False)
            try:
                evicted_engine.dispose()
                logger.info("[EnginePool] Evicted engine for connection %s", evicted_id)
            except Exception as exc:
                logger.warning("[EnginePool] Dispose failed: %s", exc)
            _close_tunnel(evicted_id)

        return engine


def invalidate_engine(connection_id: int) -> None:
    """Remove a cached engine (call when credentials change or connection deleted)."""
    with _engine_pool_lock:
        engine = _engine_pool.pop(connection_id, None)
    if engine:
        try:
            engine.dispose()
        except Exception:
            pass
    _close_tunnel(connection_id)


def _invalidate_schema_cache(connection_id: int) -> None:
    from app.services.cache import schema_cache
    with schema_cache._lock:
        keys_to_remove = [
            k for k in schema_cache._store.keys()
            if isinstance(k, tuple) and len(k) >= 2 and k[1] == connection_id
        ]
        for k in keys_to_remove:
            schema_cache._store.pop(k, None)


def engine_pool_stats() -> dict:
    with _engine_pool_lock:
        return {
            "live_engines": len(_engine_pool),
            "max_engines": MAX_ENGINES,
            "engine_pool_size": ENGINE_POOL_SIZE,
            "engine_max_overflow": ENGINE_MAX_OVERFLOW,
            "statement_timeout_ms": QUERY_STATEMENT_TIMEOUT_MS,
        }


# ── CRUD Service ─────────────────────────────────────────────────

MAX_CONNECTIONS_PER_TENANT = 25


class TenantQuotaExceeded(Exception):
    pass


class DatabaseConnectionService:
    def __init__(self, db: Session):
        self.db = db

    def list_connections(self, include_inactive: bool = False) -> List[DatabaseConnection]:
        from sqlalchemy import select
        stmt = select(DatabaseConnection).order_by(DatabaseConnection.name)
        if not include_inactive:
            stmt = stmt.where(DatabaseConnection.is_active == True)
        result = self.db.execute(stmt)
        return list(result.scalars().all())

    def count_connections(self) -> int:
        from sqlalchemy import select, func as sa_func
        result = self.db.execute(
            select(sa_func.count(DatabaseConnection.id))
            .where(DatabaseConnection.is_active == True)
        )
        return result.scalar() or 0

    def get_connection(self, connection_id: int) -> Optional[DatabaseConnection]:
        from sqlalchemy import select
        result = self.db.execute(
            select(DatabaseConnection).where(DatabaseConnection.id == connection_id)
        )
        return result.scalar_one_or_none()

    def create_connection(self, data: Dict[str, Any]) -> DatabaseConnection:
        current_count = self.count_connections()
        if current_count >= MAX_CONNECTIONS_PER_TENANT:
            raise TenantQuotaExceeded(
                f"Connection quota exceeded ({current_count}/{MAX_CONNECTIONS_PER_TENANT}). "
                "Delete unused connections or contact your administrator."
            )

        password        = data.pop("password")
        ssh_password    = data.pop("ssh_password", None)
        ssh_private_key = data.pop("ssh_private_key", None)
        ssh_passphrase  = data.pop("ssh_key_passphrase", None)

        conn = DatabaseConnection(
            **data,
            password_encrypted=encrypt_password(password),
            ssh_password_encrypted=encrypt_password(ssh_password) if ssh_password else None,
            ssh_private_key_encrypted=encrypt_password(ssh_private_key) if ssh_private_key else None,
            ssh_key_passphrase_encrypted=encrypt_password(ssh_passphrase) if ssh_passphrase else None,
        )
        self.db.add(conn)
        self.db.commit()
        self.db.refresh(conn)
        return conn

    def update_connection(
        self, connection_id: int, data: Dict[str, Any]
    ) -> Optional[DatabaseConnection]:
        conn = self.get_connection(connection_id)
        if not conn:
            return None

        if "password" in data:
            data["password_encrypted"] = encrypt_password(data.pop("password"))
        for plain, encrypted in (
            ("ssh_password",       "ssh_password_encrypted"),
            ("ssh_private_key",    "ssh_private_key_encrypted"),
            ("ssh_key_passphrase", "ssh_key_passphrase_encrypted"),
        ):
            if plain in data:
                value = data.pop(plain)
                data[encrypted] = encrypt_password(value) if value else None

        for key, value in data.items():
            if hasattr(conn, key):
                setattr(conn, key, value)

        conn.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(conn)
        invalidate_engine(connection_id)
        _invalidate_schema_cache(connection_id)
        return conn

    def delete_connection(self, connection_id: int) -> bool:
        conn = self.get_connection(connection_id)
        if not conn:
            return False
        invalidate_engine(connection_id)
        _invalidate_schema_cache(connection_id)
        self.db.delete(conn)
        self.db.commit()
        return True

    def test_connection(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Test a connection without saving it."""
        engine = None
        tunnel = None
        try:
            temp_conn = DatabaseConnection(
                id=-1,
                name="test",
                engine=data["engine"],
                host=data["host"],
                port=data["port"],
                database_name=data["database_name"],
                username=data["username"],
                password_encrypted=encrypt_password(data.get("password", "")),
                ssh_enabled=bool(data.get("ssh_enabled", False)),
                ssh_host=data.get("ssh_host"),
                ssh_port=data.get("ssh_port"),
                ssh_username=data.get("ssh_username"),
                ssh_auth_method=data.get("ssh_auth_method"),
                ssh_password_encrypted=(
                    encrypt_password(data["ssh_password"]) if data.get("ssh_password") else None
                ),
                ssh_private_key_encrypted=(
                    encrypt_password(data["ssh_private_key"]) if data.get("ssh_private_key") else None
                ),
                ssh_key_passphrase_encrypted=(
                    encrypt_password(data["ssh_key_passphrase"]) if data.get("ssh_key_passphrase") else None
                ),
            )

            host_override = port_override = None
            if temp_conn.ssh_enabled:
                tunnel = _open_tunnel(temp_conn)
                host_override = "127.0.0.1"
                port_override = tunnel.local_port

            url = build_connection_string(
                temp_conn, use_async=False,
                host_override=host_override, port_override=port_override,
            )
            engine = create_engine(url, pool_pre_ping=True)
            with engine.connect() as c:
                c.execute(text("SELECT 1"))
            return {"success": True, "message": "Connection successful"}
        except Exception as exc:
            return {"success": False, "message": str(exc)}
        finally:
            if engine is not None:
                try:
                    engine.dispose()
                except Exception:
                    pass
            if tunnel is not None:
                try:
                    tunnel.proc.terminate()
                    try:
                        tunnel.proc.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        tunnel.proc.kill()
                except Exception:
                    pass
                if tunnel.key_path:
                    try:
                        os.unlink(tunnel.key_path)
                    except Exception:
                        pass

    def update_health(self, connection_id: int) -> Dict[str, Any]:
        conn = self.get_connection(connection_id)
        if not conn:
            return {"success": False, "message": "Connection not found"}
        try:
            engine = _get_engine(conn)
            with engine.connect() as c:
                c.execute(text("SELECT 1"))
            conn.is_healthy = True
            conn.health_check_error = None
        except Exception as exc:
            conn.is_healthy = False
            conn.health_check_error = str(exc)
        conn.last_health_check = datetime.now(timezone.utc)
        self.db.commit()
        return {"success": conn.is_healthy, "message": conn.health_check_error or "OK"}


# ── Query Engine ─────────────────────────────────────────────────

HARD_ROW_LIMIT  = 10_000
HARD_BYTE_LIMIT = 50 * 1024 * 1024   # 50 MB


class QueryEngine:
    """Execute safe SELECT queries against connected databases."""

    def __init__(self, db: Session):
        self.db = db

    async def execute(
        self,
        connection_id: int,
        sql: str,
        limit: Optional[int] = None,
        user_context: Optional[Dict[str, str]] = None,
        schema_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run SQL and return Metabase-compatible result shape.

        { data: { cols: [...], rows: [...] }, row_count: N, status: "completed" }
        """
        svc = DatabaseConnectionService(self.db)
        conn = svc.get_connection(connection_id)
        if not conn:
            return self._err("Connection not found")

        # Safety validation
        try:
            query_sql = validate_sql_safe(sql)
        except SQLSafetyError as exc:
            logger.warning("[QueryEngine] Rejected unsafe SQL: %s", exc)
            return self._err(f"SQL safety check failed: {exc}")

        try:
            engine = _get_engine(conn)

            # Row-level security
            from app.services.data_access import get_active_rules, apply_rls
            active_rules = get_active_rules(self.db, connection_id)

            if active_rules:
                required = {"user_id", "permission_level_id"}
                missing  = required - set((user_context or {}).keys())
                if not user_context or missing:
                    return self._err(
                        "This database requires user authentication context. "
                        f"Missing required headers: {', '.join(sorted(missing))}"
                    )
                query_sql = apply_rls(self.db, connection_id, query_sql, user_context)
                try:
                    query_sql = validate_sql_safe(query_sql)
                except SQLSafetyError as exc:
                    logger.error("[QueryEngine] RLS produced unsafe SQL: %s", exc)
                    return self._err("Internal RLS error")
            elif user_context:
                query_sql = apply_rls(self.db, connection_id, query_sql, user_context)

            # Apply row limit
            effective_limit = min(limit or HARD_ROW_LIMIT, HARD_ROW_LIMIT)
            if "LIMIT" not in query_sql.upper():
                query_sql += f" LIMIT {effective_limit}"

            # Validate optional schema override
            safe_schema: Optional[str] = None
            if schema_name:
                if not re.match(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$", schema_name):
                    return self._err(f"Invalid schema name: {schema_name}")
                safe_schema = schema_name

            import asyncio
            dialect = conn.engine.lower()

            def _run():
                with engine.connect() as c:
                    with c.begin():
                        if safe_schema:
                            if dialect == "postgres":
                                c.execute(text(f'SET LOCAL search_path TO "{safe_schema}", public'))
                            elif dialect == "mysql":
                                c.execute(text(f"USE `{safe_schema}`"))
                        result = c.execute(text(query_sql))
                        columns = list(result.keys())
                        rows: List[list] = []
                        bytes_collected = 0
                        truncated = False
                        for row in result:
                            row_list = list(row)
                            rows.append(row_list)
                            bytes_collected += sum(
                                len(str(v)) if v is not None else 4 for v in row_list
                            )
                            if bytes_collected > HARD_BYTE_LIMIT or len(rows) >= HARD_ROW_LIMIT:
                                truncated = True
                                break
                        return columns, rows, truncated

            columns, rows, truncated = await asyncio.get_event_loop().run_in_executor(None, _run)

            cols = [
                {
                    "name": str(c),
                    "display_name": str(c).replace("_", " ").title(),
                    "base_type": "type/Text",
                }
                for c in columns
            ]
            response: Dict[str, Any] = {
                "data": {"cols": cols, "rows": rows},
                "row_count": len(rows),
                "status": "completed",
            }
            if truncated:
                response["truncated"] = True
                response["truncation_reason"] = (
                    f"Result truncated at {len(rows):,} rows "
                    f"(limit: {HARD_ROW_LIMIT:,} rows / 50 MB)"
                )
            return response

        except Exception as exc:
            logger.error("[QueryEngine] Query failed: %s", exc)
            return self._err(str(exc))

    @staticmethod
    def _err(msg: str) -> Dict[str, Any]:
        return {"data": {"cols": [], "rows": []}, "row_count": 0, "status": "failed", "error": msg}


# ── Schema Inspector ─────────────────────────────────────────────

class SchemaInspector:
    """Discover schemas, tables, and fields via SQLAlchemy inspect()."""

    def __init__(self, db: Session):
        self.db = db

    async def get_schemas(self, connection_id: int) -> List[str]:
        from app.services.cache import schema_cache
        import asyncio
        cache_key = ("schemas", connection_id)
        cached = schema_cache.get(cache_key)
        if cached is not None:
            return cached

        conn = self._get_conn(connection_id)
        engine = _get_engine(conn)

        def _run():
            return sa_inspect(engine).get_schema_names()

        schemas = await asyncio.get_event_loop().run_in_executor(None, _run)
        schema_cache.set(cache_key, schemas, ttl=600)
        return schemas

    async def get_tables(
        self,
        connection_id: int,
        schema: Optional[str] = None,
        search: str = "",
    ) -> List[Dict[str, Any]]:
        from app.services.cache import schema_cache
        import asyncio
        cache_key = ("tables", connection_id, schema or "_all_")
        cached = schema_cache.get(cache_key)
        if cached is not None:
            if search:
                s = search.lower()
                return [t for t in cached if s in t["name"].lower() or s in t["display_name"].lower()]
            return cached

        conn = self._get_conn(connection_id)
        engine = _get_engine(conn)

        def _run():
            inspector = sa_inspect(engine)
            schemas = [schema] if schema else inspector.get_schema_names()
            skip = {"information_schema", "pg_catalog", "pg_toast",
                    "mysql", "performance_schema", "sys"}
            schemas = [s for s in schemas if s not in skip]

            field_counts: Dict[str, int] = {}
            try:
                with engine.connect() as c:
                    for row in c.execute(text(
                        "SELECT table_schema, table_name, COUNT(*) AS cnt "
                        "FROM information_schema.columns "
                        "GROUP BY table_schema, table_name"
                    )):
                        field_counts[f"{row[0]}.{row[1]}"] = row[2]
            except Exception:
                pass

            tables = []
            for s in schemas:
                try:
                    for tname in inspector.get_table_names(schema=s):
                        tables.append({
                            "id": f"{s}.{tname}",
                            "name": tname,
                            "display_name": tname.replace("_", " ").title(),
                            "schema": s,
                            "db_id": connection_id,
                            "field_count": field_counts.get(f"{s}.{tname}", 0),
                        })
                except Exception as exc:
                    logger.warning("[SchemaInspector] Error listing tables for %s: %s", s, exc)
            tables.sort(key=lambda t: (t["schema"].lower(), t["name"].lower()))
            return tables

        all_tables = await asyncio.get_event_loop().run_in_executor(None, _run)
        schema_cache.set(cache_key, all_tables, ttl=300)

        if search:
            s = search.lower()
            return [t for t in all_tables if s in t["name"].lower() or s in t["display_name"].lower()]
        return all_tables

    async def get_table_fields(
        self,
        connection_id: int,
        table_name: str,
        schema: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        from app.services.cache import schema_cache
        import asyncio
        cache_key = ("fields", connection_id, schema or "_", table_name)
        cached = schema_cache.get(cache_key)
        if cached is not None:
            return cached

        conn = self._get_conn(connection_id)
        engine = _get_engine(conn)

        def _run():
            inspector = sa_inspect(engine)
            columns = inspector.get_columns(table_name, schema=schema)

            pk_cols: set = set()
            try:
                pk = inspector.get_pk_constraint(table_name, schema=schema)
                pk_cols = set(pk.get("constrained_columns", []))
            except Exception:
                pass

            fk_map: Dict[str, str] = {}
            try:
                for fk in inspector.get_foreign_keys(table_name, schema=schema):
                    for col in fk.get("constrained_columns", []):
                        fk_map[col] = (
                            f"{fk.get('referred_table', '')}."
                            f"{','.join(fk.get('referred_columns', []))}"
                        )
            except Exception:
                pass

            fields = []
            for col in columns:
                col_name = col["name"]
                col_type = str(col.get("type", "VARCHAR"))
                base_type = _map_base_type(col_type)
                semantic_type = None
                if col_name in pk_cols:
                    semantic_type = "type/PK"
                elif col_name in fk_map:
                    semantic_type = "type/FK"
                qualified = f"{schema or ''}.{table_name}.{col_name}"
                field_id = abs(hash(qualified)) % (2**31)
                fields.append({
                    "id": field_id,
                    "name": col_name,
                    "display_name": col_name.replace("_", " ").title(),
                    "base_type": base_type,
                    "semantic_type": semantic_type,
                    "database_type": col_type,
                    "fk_target": fk_map.get(col_name),
                })
            return fields

        fields = await asyncio.get_event_loop().run_in_executor(None, _run)
        schema_cache.set(cache_key, fields, ttl=600)
        return fields

    async def get_metadata(self, connection_id: int) -> Dict[str, Any]:
        conn = self._get_conn(connection_id)
        tables = self.get_tables(connection_id)
        return {"id": conn.id, "name": conn.name, "engine": conn.engine, "tables": tables}

    async def _get_conn(self, connection_id: int) -> DatabaseConnection:
        svc = DatabaseConnectionService(self.db)
        conn = svc.get_connection(connection_id)
        if not conn:
            raise ValueError(f"Database connection {connection_id} not found")
        return conn


def _map_base_type(sql_type: str) -> str:
    t = sql_type.upper()
    if any(x in t for x in ("INT", "SERIAL", "BIGINT", "SMALLINT")):
        return "type/Integer"
    if any(x in t for x in ("FLOAT", "DOUBLE", "DECIMAL", "NUMERIC", "REAL")):
        return "type/Float"
    if "BOOL" in t:
        return "type/Boolean"
    if "DATE" in t and "TIME" not in t:
        return "type/Date"
    if any(x in t for x in ("TIMESTAMP", "DATETIME")):
        return "type/DateTime"
    if "TIME" in t and "STAMP" not in t:
        return "type/Time"
    if any(x in t for x in ("JSON", "JSONB")):
        return "type/Structured"
    return "type/Text"
