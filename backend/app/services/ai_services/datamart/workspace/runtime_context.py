"""
Per-request datamart warehouse context (tenant profile, engine, query schemas).

Uses contextvars so sync pipeline code and thread-pool workers share one resolved
connection without changing every function signature. Legacy single-schema mode
remains the fallback when no context is set.
"""
from __future__ import annotations

import logging
import time
from contextvars import ContextVar, Token
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Optional, TypeVar

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.core.config import settings

from .. import config as dm_config

logger = logging.getLogger("ai_services.datamart.runtime")

T = TypeVar("T")

_datamart_ctx: ContextVar[Optional["DatamartRuntimeContext"]] = ContextVar(
    "datamart_runtime",
    default=None,
)

# Bootstrap / introspection cache: (tenant_id, profile, fingerprint) -> payload
_metadata_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_METADATA_CACHE_TTL_SEC = int(
    getattr(dm_config, "DATAMART_METADATA_CACHE_TTL_SEC", 0) or 0
) or 900

_engine_cache: dict[str, Engine] = {}


def _warehouse_engine_connect_args() -> dict[str, Any]:
    return {
        "connect_timeout": max(3, dm_config.WAREHOUSE_CONNECT_TIMEOUT_SEC),
        "options": (
            f"-c statement_timeout={max(5000, dm_config.WAREHOUSE_STATEMENT_TIMEOUT_SEC * 1000)}"
        ),
    }


class DatamartProfile(str, Enum):
    LEGACY_AUDIT = "legacy_audit"
    TENANT_ETL = "tenant_etl"


@dataclass(frozen=True)
class DatamartRuntimeContext:
    tenant_id: str
    profile: DatamartProfile
    engine: Engine
    query_schemas: tuple[str, ...]
    primary_schema: str
    database_name: str

    @property
    def is_tenant_etl(self) -> bool:
        return self.profile == DatamartProfile.TENANT_ETL

    @property
    def allowed_schemas_lower(self) -> frozenset[str]:
        return frozenset(s.lower() for s in self.query_schemas)


def get_datamart_context() -> Optional[DatamartRuntimeContext]:
    return _datamart_ctx.get()


def require_datamart_context() -> DatamartRuntimeContext:
    ctx = get_datamart_context()
    if ctx is not None:
        return ctx
    return resolve_datamart_context(dm_config.DATAMART_DEFAULT_TENANT_ID)


def set_datamart_context(ctx: DatamartRuntimeContext) -> Token:
    return _datamart_ctx.set(ctx)


def reset_datamart_context(token: Token) -> None:
    try:
        _datamart_ctx.reset(token)
    except ValueError:
        # FastAPI runs sync yield-deps setup/teardown in different worker threads.
        _datamart_ctx.set(None)


def run_with_datamart_context(tenant_id: str, fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """Resolve tenant warehouse context, run ``fn``, then reset context (thread-safe)."""
    ctx = resolve_datamart_context(tenant_id)
    token = set_datamart_context(ctx)
    try:
        return fn(*args, **kwargs)
    finally:
        reset_datamart_context(token)


def _profile_from_env() -> str:
    return (dm_config.DATAMART_PROFILE or "auto").strip().lower()


def _tenant_etl_schemas() -> tuple[str, ...]:
    return dm_config.parse_query_schemas()


def _legacy_schema() -> str:
    """Deprecated legacy_audit profile only (DATAMART_SCHEMA or primary tenant schema)."""
    legacy = (dm_config.WAREHOUSE_SCHEMA or "").strip()
    if legacy:
        return legacy
    return dm_config.primary_schema_name()


def _engine_cache_key(profile: DatamartProfile, tenant_id: str, database: str) -> str:
    return f"{profile.value}:{tenant_id}:{database}"


def _tenant_warehouse_database_name(tenant_id: str) -> str:
    """Per-tenant analytics DB (hrm_wh_{tenant_id}) from registry or platform default."""
    from app.core.warehouse import default_warehouse_db_name, get_layout_sync

    tid = (tenant_id or dm_config.DATAMART_DEFAULT_TENANT_ID).strip()
    try:
        layout = get_layout_sync(tid)
        if layout.database_name:
            return layout.database_name
    except Exception as exc:  # noqa: BLE001
        logger.debug("layout lookup for %s: %s", tid, exc)
    return default_warehouse_db_name(tid)


def _warehouse_sync_url(database: str) -> str:
    db = (database or "").strip()
    return (
        f"postgresql+psycopg2://{dm_config.WAREHOUSE_USER}:{dm_config.WAREHOUSE_PASSWORD}"
        f"@{dm_config.WAREHOUSE_HOST}:{dm_config.WAREHOUSE_PORT}/{db}"
    )


def _engine_from_datamart_env() -> tuple[Engine, str]:
    url = dm_config.WAREHOUSE_DATABASE_URL
    db = dm_config.WAREHOUSE_DB
    key = _engine_cache_key(DatamartProfile.LEGACY_AUDIT, "_env", db)
    if key not in _engine_cache:
        _engine_cache[key] = create_engine(
            url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=5,
            connect_args=_warehouse_engine_connect_args(),
        )
        logger.debug("Datamart engine (env): db=%s", db)
    return _engine_cache[key], db


def tenant_registry_available(tenant_id: str) -> bool:
    """True when hrm_control.tenant_registry has a dedicated warehouse for the tenant."""
    try:
        from app.core.warehouse import get_layout_sync

        layout = get_layout_sync(tenant_id)
        return bool(layout.uses_dedicated_database and layout.database_name)
    except Exception as exc:  # noqa: BLE001
        logger.debug("tenant_registry lookup failed for %s: %s", tenant_id, exc)
        return False


def _engine_for_tenant_registry(tenant_id: str) -> Optional[tuple[Engine, str]]:
    if not tenant_registry_available(tenant_id):
        return None
    try:
        from app.core.warehouse import connection_params, get_warehouse_engine_sync

        params = connection_params(tenant_id)
        db_name = (params.get("database") or "").strip()
        if not db_name:
            return None
        engine = get_warehouse_engine_sync(tenant_id, provision=False)
        return engine, db_name
    except Exception as exc:  # noqa: BLE001
        logger.debug("Registry warehouse engine unavailable for %s: %s", tenant_id, exc)
        return None


def _env_tenant_etl_engine(
    tenant_id: str,
    env_engine: Engine,
    database: str,
) -> tuple[Engine, str]:
    """Engine from DATAMART_DB_* host/credentials targeting ``database`` (per tenant)."""
    db = (database or "").strip() or _tenant_warehouse_database_name(tenant_id)
    key = _engine_cache_key(DatamartProfile.TENANT_ETL, tenant_id, db)
    if key not in _engine_cache:
        url = _warehouse_sync_url(db)
        _engine_cache[key] = create_engine(
            url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=5,
            connect_args=_warehouse_engine_connect_args(),
        )
        logger.debug("Datamart engine (tenant_etl env): tenant=%s db=%s", tenant_id, db)
    return _engine_cache[key], db


def _legacy_runtime_context(
    tenant_id: str,
    env_engine: Engine,
    env_db: str,
) -> DatamartRuntimeContext:
    legacy_schema = _legacy_schema()
    logger.info(
        "Datamart context tenant=%s profile=legacy_audit db=%s schema=%s",
        tenant_id,
        env_db,
        legacy_schema,
    )
    return DatamartRuntimeContext(
        tenant_id=tenant_id,
        profile=DatamartProfile.LEGACY_AUDIT,
        engine=env_engine,
        query_schemas=(legacy_schema,),
        primary_schema=legacy_schema,
        database_name=env_db,
    )


def _db_name_looks_like_tenant_warehouse(db_name: str) -> bool:
    prefix = (settings.WAREHOUSE_DB_PREFIX or "hrm_wh_").strip()
    return bool(db_name) and db_name.startswith(prefix)


def probe_tenant_etl_ready(engine: Engine, schemas: tuple[str, ...]) -> bool:
    """Read-only: True if at least one analytics schema has a user table/view."""
    check_schemas = schemas or ("hr_semantic", "hr")
    try:
        with engine.connect() as conn:
            for schema in check_schemas:
                row = conn.execute(
                    text(
                        """
                        SELECT 1
                        FROM information_schema.tables
                        WHERE table_schema = :schema
                          AND table_type IN ('BASE TABLE', 'VIEW')
                        LIMIT 1
                        """
                    ),
                    {"schema": schema},
                ).first()
                if row:
                    return True
    except Exception as exc:  # noqa: BLE001
        logger.debug("tenant_etl_ready probe failed: %s", exc)
    return False


def _schema_fingerprint(engine: Engine, schemas: tuple[str, ...]) -> str:
    counts: list[str] = []
    try:
        with engine.connect() as conn:
            for schema in schemas:
                n = conn.execute(
                    text(
                        """
                        SELECT COUNT(*)::int
                        FROM information_schema.tables
                        WHERE table_schema = :schema
                          AND table_type IN ('BASE TABLE', 'VIEW')
                        """
                    ),
                    {"schema": schema},
                ).scalar()
                counts.append(f"{schema}:{int(n or 0)}")
    except Exception:
        return "unknown"
    return "|".join(counts)


def _tenant_etl_ready_via_registry(tenant_id: str) -> bool:
    if not tenant_registry_available(tenant_id):
        return False
    registry = _engine_for_tenant_registry(tenant_id)
    return bool(registry and probe_tenant_etl_ready(registry[0], _tenant_etl_schemas()))


def _tenant_etl_ready_via_env(env_db: str) -> bool:
    if not _db_name_looks_like_tenant_warehouse(env_db):
        return False
    eng, _ = _engine_from_datamart_env()
    return probe_tenant_etl_ready(eng, _tenant_etl_schemas())


def _prefer_tenant_registry() -> bool:
    """When true (default), registry wins over DATAMART_DB_* for profile and engine."""
    return dm_config.DATAMART_PREFER_TENANT_REGISTRY


def _resolve_profile(tenant_id: str, *, env_db: str) -> DatamartProfile:
    explicit = _profile_from_env()
    registry_only = dm_config.DATAMART_USE_TENANT_REGISTRY
    prefer_registry = _prefer_tenant_registry()

    def _registry_etl_ready() -> bool:
        return _tenant_etl_ready_via_registry(tenant_id)

    def _env_etl_ready() -> bool:
        return _tenant_etl_ready_via_env(env_db)

    def _pick_tenant_etl() -> DatamartProfile:
        if registry_only:
            if _registry_etl_ready():
                return DatamartProfile.TENANT_ETL
            return (
                DatamartProfile.LEGACY_AUDIT
                if dm_config.DATAMART_LEGACY_FALLBACK
                else DatamartProfile.TENANT_ETL
            )
        if prefer_registry:
            if _registry_etl_ready():
                return DatamartProfile.TENANT_ETL
            if _env_etl_ready():
                return DatamartProfile.TENANT_ETL
        else:
            if _env_etl_ready():
                return DatamartProfile.TENANT_ETL
            if _registry_etl_ready():
                return DatamartProfile.TENANT_ETL
        return (
            DatamartProfile.LEGACY_AUDIT
            if dm_config.DATAMART_LEGACY_FALLBACK
            else DatamartProfile.TENANT_ETL
        )

    if explicit == DatamartProfile.LEGACY_AUDIT.value:
        return DatamartProfile.LEGACY_AUDIT
    if explicit == DatamartProfile.TENANT_ETL.value:
        return _pick_tenant_etl()

    picked = _pick_tenant_etl()
    if picked == DatamartProfile.TENANT_ETL:
        return DatamartProfile.TENANT_ETL
    if registry_only:
        return picked
    if dm_config.DATAMART_LEGACY_FALLBACK:
        return DatamartProfile.LEGACY_AUDIT
    eng, _ = _engine_from_datamart_env()
    if probe_tenant_etl_ready(eng, _tenant_etl_schemas()):
        return DatamartProfile.TENANT_ETL
    return DatamartProfile.TENANT_ETL


def resolve_datamart_context(tenant_id: str) -> DatamartRuntimeContext:
    tid = (tenant_id or dm_config.DATAMART_DEFAULT_TENANT_ID).strip()
    env_engine, env_db = _engine_from_datamart_env()
    profile = _resolve_profile(tid, env_db=env_db)

    if profile == DatamartProfile.TENANT_ETL:
        schemas = _tenant_etl_schemas()
        primary = (dm_config.DATAMART_PRIMARY_SCHEMA or "hr_semantic").strip()
        if primary not in schemas:
            primary = schemas[0]

        tenant_db = _tenant_warehouse_database_name(tid)
        registry = _engine_for_tenant_registry(tid)
        env_etl = _env_tenant_etl_engine(tid, env_engine, tenant_db)
        if _prefer_tenant_registry():
            if registry:
                engine, database_name = registry
            elif dm_config.DATAMART_USE_TENANT_REGISTRY:
                logger.warning(
                    "tenant_etl for %s: registry engine unavailable — using DATAMART_DB_* "
                    "at %s (seed: python tools/seed_demo_tenant_registry_warehouse.py)",
                    tid,
                    tenant_db,
                )
                if dm_config.DATAMART_LEGACY_FALLBACK:
                    return _legacy_runtime_context(tid, env_engine, env_db)
                engine, database_name = env_etl
            else:
                engine, database_name = env_etl
        else:
            if env_etl and probe_tenant_etl_ready(env_etl[0], schemas):
                engine, database_name = env_etl
            elif registry:
                engine, database_name = registry
            elif dm_config.DATAMART_USE_TENANT_REGISTRY:
                logger.warning(
                    "tenant_etl for %s: using DATAMART_DB_* at %s",
                    tid,
                    tenant_db,
                )
                if dm_config.DATAMART_LEGACY_FALLBACK:
                    return _legacy_runtime_context(tid, env_engine, env_db)
                engine, database_name = env_etl
            else:
                engine, database_name = env_etl

        logger.info(
            "Datamart context tenant=%s profile=tenant_etl db=%s schemas=%s",
            tid,
            database_name,
            ",".join(schemas),
        )
        return DatamartRuntimeContext(
            tenant_id=tid,
            profile=profile,
            engine=engine,
            query_schemas=schemas,
            primary_schema=primary,
            database_name=database_name,
        )

    return _legacy_runtime_context(tid, env_engine, env_db)


def mart_schema_for_hints() -> str:
    """Schema prefix used in join-hint text (hr for ETL marts, legacy schema otherwise)."""
    ctx = get_datamart_context()
    if ctx is not None:
        if ctx.is_tenant_etl:
            layout_hr = "hr"
            if layout_hr in ctx.query_schemas:
                return layout_hr
            return ctx.primary_schema
        return ctx.primary_schema
    return _legacy_schema()


def database_prompt_section() -> str:
    """System-prompt database section for current context."""
    ctx = get_datamart_context()
    if ctx is None:
        return f"Schema: {_legacy_schema()}"
    if ctx.is_tenant_etl:
        schema_list = ", ".join(ctx.query_schemas)
        return (
            f"PostgreSQL database: {ctx.database_name}\n"
            f"Query schemas: {schema_list}\n"
            f"Primary schema (default qualification): {ctx.primary_schema}\n"
            "Routing:\n"
            f"- Prefer {ctx.primary_schema}.vw_* views for summary/KPI-style questions.\n"
            "- Use hr.dim_*, hr.fact_*, hr.mart_* for detailed mart tables and joins.\n"
            "- Use hr_snap.snap_* for historical / as-of questions "
            "(filter with dbt_valid_from / dbt_valid_to when needed).\n"
            "- Always qualify tables as schema.table_name using one of the query schemas above.\n"
            f"- NEVER use {ctx.database_name}.schema.table (three-part names). The session is "
            f"already connected to database {ctx.database_name}; only hr.* / hr_semantic.* / "
            "hr_snap.* are valid."
        )
    return f"Schema: {ctx.primary_schema}"


def sql_qualification_rule() -> str:
    ctx = get_datamart_context()
    if ctx is not None and ctx.is_tenant_etl:
        return (
            "Always qualify table names with schema.table_name "
            f"(allowed schemas: {', '.join(ctx.query_schemas)})."
        )
    schema = ctx.primary_schema if ctx else _legacy_schema()
    return f"Always qualify table names with the schema: {schema}.table_name"


def sync_datamart_metadata(tenant_id: str, *, force_refresh: bool = False) -> dict[str, Any]:
    """
    Read-only introspection for bootstrap (Sync button / GET /datamart/bootstrap).

    For every schema in ``ctx.query_schemas`` (e.g. hr_semantic, hr, hr_snap), counts
    both base tables and views via ``relations_in_schema``. Uses in-memory TTL cache.
    """
    ctx = resolve_datamart_context(tenant_id)
    fingerprint = _schema_fingerprint(ctx.engine, ctx.query_schemas)
    cache_key = f"{tenant_id}:{ctx.profile.value}:{fingerprint}"
    now = time.time()
    if not force_refresh:
        cached = _metadata_cache.get(cache_key)
        if cached and (now - cached[0]) < _METADATA_CACHE_TTL_SEC:
            return cached[1]

    from sqlalchemy import inspect as sa_inspect

    from ..schema import relations_in_schema

    table_counts: dict[str, int] = {}
    total_tables = 0
    try:
        inspector = sa_inspect(ctx.engine)
        for schema in ctx.query_schemas:
            names = relations_in_schema(inspector, schema)
            table_counts[schema] = len(names)
            total_tables += len(names)
    except Exception as exc:  # noqa: BLE001
        logger.warning("sync_datamart_metadata failed: %s", exc)

    logger.info(
        "datamart metadata sync tenant=%s db=%s profile=%s schemas=%s "
        "relation_counts=%s total=%s ready=%s",
        tenant_id,
        ctx.database_name,
        ctx.profile.value,
        ",".join(ctx.query_schemas),
        table_counts,
        total_tables,
        total_tables > 0,
    )

    payload = {
        "tenant_id": tenant_id,
        "profile": ctx.profile.value,
        "database_name": ctx.database_name,
        "query_schemas": list(ctx.query_schemas),
        "primary_schema": ctx.primary_schema,
        "table_counts": table_counts,
        "total_tables": total_tables,
        "ready": total_tables > 0,
        "synced_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "fingerprint": fingerprint,
    }
    _metadata_cache[cache_key] = (now, payload)
    return payload


def clear_metadata_cache_for_tests() -> None:
    _metadata_cache.clear()


def invalidate_datamart_metadata_caches(tenant_id: str) -> None:
    """Drop bootstrap TTL cache, semantic YAML LRU, and warehouse engines after ops sync."""
    clear_metadata_cache_for_tests()
    try:
        from ..schema import clear_warehouse_table_list_cache

        clear_warehouse_table_list_cache()
    except Exception:
        pass
    try:
        from ..semantic.semantic_layer import clear_catalog_cache

        clear_catalog_cache()
    except Exception:
        pass
    invalidate_datamart_engines_for_tenant(tenant_id)


def invalidate_datamart_engines_for_tests() -> None:
    for eng in _engine_cache.values():
        try:
            eng.dispose()
        except Exception:
            pass
    _engine_cache.clear()
    try:
        from app.core.warehouse import invalidate_tenant_cache

        invalidate_tenant_cache(dm_config.DATAMART_DEFAULT_TENANT_ID)
    except Exception:
        pass


def invalidate_datamart_engines_for_tenant(tenant_id: str) -> None:
    """Drop cached warehouse engines for one tenant (after registry / .env changes)."""
    tid = (tenant_id or "").strip()
    if not tid:
        return
    keys = [k for k in _engine_cache if f":{tid}:" in k]
    for key in keys:
        eng = _engine_cache.pop(key, None)
        if eng is not None:
            try:
                eng.dispose()
            except Exception:
                pass
    try:
        from app.core.warehouse import invalidate_tenant_cache

        invalidate_tenant_cache(tid)
    except Exception:
        pass
