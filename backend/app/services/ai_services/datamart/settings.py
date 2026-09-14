"""
Datamart runtime settings — single source of truth.

Only warehouse connectivity, tenant routing, LLM models, and a small set of
pipeline toggles are configurable via environment variables. Everything else
uses fixed production defaults in code.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from app.core.config import settings as app_settings


def _flag(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes")


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


@dataclass(frozen=True, slots=True)
class DatamartSettings:
    # Warehouse (per-tenant DB)
    warehouse_host: str
    warehouse_port: str
    warehouse_user: str
    warehouse_password: str
    warehouse_db: str
    default_tenant_id: str
    default_user_id: str
    require_tenant_header: bool
    profile: str
    query_schemas: str
    primary_schema: str
    legacy_fallback: bool
    metadata_cache_ttl_sec: int
    use_tenant_registry: bool
    prefer_tenant_registry: bool

    # DataHub
    datahub_gms_url: str
    datahub_gms_token: str
    datahub_timeout_sec: int
    use_datahub: str
    table_list_cache_ttl_sec: int

    # LLM
    chat_model: str
    template_model: str
    repair_model: str
    llm_context_tokens: int
    llm_completion_reserve: int
    chars_per_token: float
    max_sql_retries: int
    warehouse_connect_timeout_sec: int
    warehouse_statement_timeout_sec: int

    # Pipeline (minimal surface)
    block_on_insufficient_retrieval: bool
    require_sql_adequacy: bool
    max_repair_attempts_per_turn: int
    clarify_on_ambiguous: bool
    clarification_ui: bool
    log_llm_context: bool
    debug_log_llm_context_max_chars: int
    prefer_deterministic_sql: bool
    schema_catalog_first: bool
    report_spec_enabled: bool
    tier_c_query_plan: bool
    tier_c_slim_prompt: bool
    block_stub_sql: bool
    verified_min_score: int

    # Broker / results
    broker_max_tables: int
    broker_max_tables_topic: int
    max_result_rows: int


def load_settings() -> DatamartSettings:
    default_tenant = os.getenv("DATAMART_DEFAULT_TENANT_ID", "demo_tenant").strip()
    wh_prefix = (getattr(app_settings, "WAREHOUSE_DB_PREFIX", None) or "hrm_wh_").strip()
    default_db = f"{wh_prefix}{default_tenant}"
    chat_model = os.getenv("DATAMART_CHAT_MODEL") or os.getenv(
        "DATAMART_LLM_MODEL", "gpt-oss"
    )

    return DatamartSettings(
        warehouse_host=os.getenv("DATAMART_DB_HOST", "139.162.17.40"),
        warehouse_port=os.getenv("DATAMART_DB_PORT", "10000"),
        warehouse_user=os.getenv("DATAMART_DB_USER", "mint_bi_reader"),
        warehouse_password=os.getenv("DATAMART_DB_PASSWORD", ""),
        warehouse_db=os.getenv("DATAMART_DB_NAME", default_db),
        default_tenant_id=default_tenant,
        default_user_id=os.getenv("DATAMART_DEFAULT_USER_ID", "default-user"),
        require_tenant_header=_flag("DATAMART_REQUIRE_TENANT_HEADER"),
        profile=os.getenv("DATAMART_PROFILE", "tenant_etl"),
        query_schemas=os.getenv("DATAMART_QUERY_SCHEMAS", "hr_semantic,hr,hr_snap"),
        primary_schema=os.getenv("DATAMART_PRIMARY_SCHEMA", "hr_semantic"),
        legacy_fallback=_flag("DATAMART_LEGACY_FALLBACK"),
        metadata_cache_ttl_sec=_int("DATAMART_METADATA_CACHE_TTL_SEC", 900),
        use_tenant_registry=_flag("DATAMART_USE_TENANT_REGISTRY", "true"),
        prefer_tenant_registry=_flag("DATAMART_PREFER_TENANT_REGISTRY", "true"),
        datahub_gms_url=os.getenv("DATAHUB_GMS_URL", "http://localhost:8080"),
        datahub_gms_token=os.getenv("DATAHUB_GMS_TOKEN", ""),
        datahub_timeout_sec=_int("DATAHUB_TIMEOUT_SECONDS", 5),
        use_datahub=os.getenv("DATAMART_USE_DATAHUB", "auto").strip().lower(),
        table_list_cache_ttl_sec=_int("DATAMART_TABLE_LIST_CACHE_TTL_SEC", 300),
        chat_model=chat_model,
        template_model=os.getenv("DATAMART_TEMPLATE_MODEL", chat_model),
        repair_model=os.getenv("DATAMART_REPAIR_MODEL", chat_model),
        llm_context_tokens=_int("DATAMART_LLM_CONTEXT_TOKENS", 8192),
        llm_completion_reserve=_int("DATAMART_LLM_COMPLETION_RESERVE", 900),
        chars_per_token=float(os.getenv("DATAMART_CHARS_PER_TOKEN", "3.2")),
        max_sql_retries=_int("DATAMART_MAX_SQL_RETRIES", 1),
        warehouse_connect_timeout_sec=_int("DATAMART_WAREHOUSE_CONNECT_TIMEOUT_SEC", 15),
        warehouse_statement_timeout_sec=_int(
            "DATAMART_WAREHOUSE_STATEMENT_TIMEOUT_SEC", 60
        ),
        block_on_insufficient_retrieval=_flag(
            "DATAMART_BLOCK_INSUFFICIENT_RETRIEVAL", "true"
        ),
        require_sql_adequacy=_flag("DATAMART_REQUIRE_SQL_ADEQUACY", "true"),
        max_repair_attempts_per_turn=_int("DATAMART_MAX_REPAIR_ATTEMPTS_PER_TURN", 1),
        clarify_on_ambiguous=_flag("DATAMART_CLARIFY_ON_AMBIGUOUS", "true"),
        clarification_ui=_flag("DATAMART_CLARIFICATION_UI", "true"),
        log_llm_context=_flag("DATAMART_LOG_LLM_CONTEXT"),
        debug_log_llm_context_max_chars=_int(
            "DATAMART_LOG_LLM_CONTEXT_MAX_CHARS", 24000
        ),
        prefer_deterministic_sql=_flag("DATAMART_PREFER_DETERMINISTIC_SQL", "true"),
        schema_catalog_first=_flag("DATAMART_SCHEMA_CATALOG_FIRST", "true"),
        report_spec_enabled=_flag("DATAMART_REPORT_SPEC_ENABLED", "true"),
        tier_c_query_plan=_flag("DATAMART_TIER_C_QUERY_PLAN", "true"),
        tier_c_slim_prompt=_flag("DATAMART_TIER_C_SLIM_PROMPT", "true"),
        block_stub_sql=_flag("DATAMART_BLOCK_STUB_SQL", "true"),
        verified_min_score=_int("DATAMART_VERIFIED_MIN_SCORE", 6),
        broker_max_tables=_int("DATAMART_BROKER_MAX_TABLES", 8),
        broker_max_tables_topic=_int("DATAMART_BROKER_MAX_TABLES_TOPIC", 10),
        max_result_rows=500,
    )


# Module singleton
SETTINGS: DatamartSettings = load_settings()
