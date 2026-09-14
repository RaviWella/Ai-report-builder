"""Application settings (env-driven).

Two database URLs are deliberately separate (README §10):
- METADATA_DB_URL  -> the app's own PostgreSQL (semantic layer, report defs, audit)
- DATAMART_RO_URL  -> the reporting read replica, connected with a READ-ONLY user.

Reporting queries must NEVER run on the metadata DB or the datamart primary.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- App ---
    app_name: str = "MintHRM Report Builder"
    environment: str = "local"  # local | staging | production
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    # --- Metadata DB (schema-per-tenant PostgreSQL) ---
    metadata_db_url: str = Field(
        default="postgresql+psycopg://app:app@localhost:5432/minthrm_reports",
        description="App metadata DB (PostgreSQL 16/17), schema-per-tenant.",
    )
    pg_template_schema: str = "public"
    pg_auto_migrate: bool = False
    pg_allow_unregistered_tenants: bool = True
    pg_provision_api_key: str = ""
    # Per Gunicorn/Celery process. Production runs 4 Uvicorn workers, so
    # max checkouts ≈ workers × (size + overflow). Keep Postgres max_connections
    # above that plus Celery (see .env.example).
    pg_pool_size: int = 5
    pg_pool_max_overflow: int = 15
    pg_pool_timeout_seconds: int = 10
    pg_pool_recycle_seconds: int = 1800

    @property
    def is_development(self) -> bool:
        return self.environment in ("local", "development")

    # --- Datamart read replica (READ-ONLY user) ---
    datamart_ro_url: str = Field(
        default="postgresql+psycopg://warehouse_user:CHANGE_ME@65.108.38.187:5432/mint_control",
        description="Datamart read replica DSN. Must be a read-only DB user.",
    )
    # Per-tenant the datamart is physically its own database `mint_{tenant_key}`
    # (core/mart/meta schemas). The resolver in db/datamart.py turns a tenant into
    # a scope by substituting this database name.
    datamart_db_pattern: str = Field(
        default="mint_{tenant_key}",
        description="Per-tenant database name pattern; '' means single-DB schema scoping.",
    )
    # Consumer surface = the denormalised `mart` schema (report-ready mart_* tables);
    # `core` holds the dims/facts used by curated SQL (e.g. bank instructions).
    datamart_schema_semantic: str = "mart"
    datamart_schema_core: str = "core"
    # Defense-in-depth (WS-4): when set, every datamart session downgrades to this
    # DB role (`SET ROLE`), which is granted SELECT only on the semantic/mart
    # schemas — so even an app-layer bug can't write or read raw/staging tables.
    # Empty = off (the login user's own privileges apply). See infra/datamart/ai_reader_role.sql.
    datamart_readonly_role: str = ""
    # WS-3: a load-watermark query whose single scalar (a max load/refresh time) is
    # recorded as the `datamart_snapshot_ref` on every run, so "reproduce this exact
    # report" means same catalogue version AND same data snapshot. Best-effort:
    # failures are swallowed (snapshot left null), never breaking a run.
    datamart_watermark_query: str = (
        "SELECT max(last_run_at) FROM meta.load_watermark"
    )

    # --- Query Engine guards (NFR-1, NFR-3) ---
    query_row_limit: int = 50_000
    preview_row_limit: int = 100
    query_statement_timeout_ms: int = 30_000
    datamart_pool_size: int = 5
    datamart_pool_max_overflow: int = 5
    # L6 — query cost governor (noisy-neighbour / runaway-query guard). OFF by
    # default. When enabled, a full run is EXPLAINed first (planner only, the query
    # is not executed); if the planner's total cost exceeds the threshold the run is
    # refused with a clear message before it can saturate the shared datamart. A
    # threshold of 0 also means "no limit". Tune from real plan costs (see the L0
    # slow-query view). Previews (capped at preview_row_limit) are never guarded.
    query_cost_guard_enabled: bool = False
    query_max_estimated_cost: float = 0.0
    # G1 — governance: enforce each field's declared `allowed_aggregations`. OFF by
    # default. When enabled, a value-aggregation (SUM/AVG/MIN/MAX) on a field is
    # refused unless that function is in the field's allowed list — so a dynamic
    # report can't produce a nonsensical number (AVG of an ID, SUM of a rate).
    # COUNT / COUNT DISTINCT are always allowed (counting any field is valid).
    query_enforce_allowed_aggregations: bool = False
    # L1 — require a period filter on reports that read period-grained marts
    # (payroll / paysheet / attendance …). OFF by default. When enabled, such a
    # report must filter on a period field (year/month) — static or runtime param —
    # so it can't silently scan all history (the single biggest avoidable scan).
    # A report with no period-grained entity is unaffected.
    query_require_period_filter: bool = False

    # --- Redis / Celery ---
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # --- Result cache (Redis) ---
    # Caches report QueryResults so identical runs don't re-hit the flaky per-tenant
    # datamart. Correct-by-construction: the datamart load-watermark
    # (datamart_snapshot_ref) is PART of the key, so a warehouse refresh changes the
    # key and stale entries become unreachable — no explicit invalidation, and a
    # stale snapshot is never served. The TTL is only a safety net. We cache ONLY
    # when a snapshot_ref is available (otherwise freshness can't be anchored).
    result_cache_enabled: bool = True
    result_cache_url: str = "redis://localhost:6379/3"
    result_cache_ttl_seconds: int = 6 * 3600  # safety net; snapshot keying does the real invalidation
    result_cache_watermark_ttl_seconds: int = 60  # how long a tenant's freshness watermark is reused
    result_cache_max_bytes: int = 5 * 1024 * 1024  # don't cache results larger than this (compressed)
    result_cache_lock_ttl_seconds: int = 30  # single-flight lock lifetime
    result_cache_wait_ms: int = 3000  # how long a waiter blocks for the in-flight computation

    # Shared (Redis) cache for a tenant's resolved datamart_key — production runs
    # multiple workers, so a per-process cache would leave every OTHER worker
    # serving a stale key after a fix with no way to force a refresh short of a
    # restart. TTL is a safety net; explicit invalidation is the real mechanism
    # (see tenant_scope.clear_datamart_key_cache).
    datamart_key_cache_ttl_seconds: int = 300

    # --- Auth (OAuth2 / JWT) ---
    # In production the parent MintHRM platform authenticates the caller and the
    # identity arrives in the `Authorization: Bearer <JWT>` header (validated here).
    jwt_secret: str = "CHANGE_ME_dev_only_secret"
    jwt_algorithm: str = "HS256"
    jwt_access_ttl_seconds: int = 900  # align with HRIS REPORT_BUILDER_JWT_TTL
    jwt_refresh_leeway_seconds: int = 86400  # match HRIS PHP session timeout; refresh is the source of truth
    hris_refresh_timeout_seconds: float = 10.0  # outbound HRIS refresh call timeout

    # --- Local dev auth bypass (NEVER honoured when environment == "production") ---
    # When on, requests need no token and run as the hardcoded identity below, so
    # the module can be browsed locally without a login screen.
    dev_auth_bypass: bool = False
    dev_tenant_id: str = "demo_tenant"
    dev_user_id: str = "dev-user"
    dev_role: str = "client_hr_admin"  # support_admin | client_hr_admin | client_end_user

    # --- AI Adapter (defaults; per-tenant overrides live in ai_provider_configs) ---
    ai_provider: str = "anthropic"  # anthropic | selfhosted
    ai_model: str = "claude-opus-4-8"
    ai_max_tokens: int = 2400  # room for many-column mappings; still fits mimo-v2.5 4k context
    anthropic_api_key: str = ""  # optional fallback; UI-entered keys take precedence
    # Fernet key for encrypting UI-entered AI API keys at rest (managed secret).
    ai_config_enc_key: str = ""
    # Self-hosted (vLLM) OpenAI-compatible endpoint when ai_provider == "selfhosted"
    selfhosted_base_url: str = "http://localhost:8001/v1"
    selfhosted_model: str = "mimo-v2.5"
    selfhosted_api_key: str = ""  # optional Bearer token for internal AI proxy / gateway
    # Total context window of the self-hosted model (input + output must fit).
    # mimo-v2.5 on the proxy is 4096; raise this for larger-context models.
    selfhosted_context: int = 4096
    # Optional hard cap on OUTPUT tokens for the self-hosted model. 0 (default) =
    # omit max_tokens entirely — the model stops naturally (finish_reason=stop) and
    # long JSON responses aren't truncated. Set a positive value only to force a cap.
    selfhosted_max_tokens: int = 0

    # --- AI-assisted Rule Report chat (Claude Code, via claude-agent-sdk) ---
    # A separate model/track from the ai_* DataSpec settings above: this drives the
    # rule-engine JSON builder, using the Claude Code CLI (installed in the image,
    # see backend/Dockerfile) rather than a plain chat-completion call.
    rule_ai_model: str = Field(default="claude-sonnet-5", alias="RULE_AI_MODEL")
    # "subscription" (the Claude Code CLI's own login on the backend host — a Max
    # plan; no API key) or "api_key" (our ai-proxy, via anthropic_api_key/_base_url).
    rule_ai_auth_mode: str = Field(default="subscription", alias="RULE_AI_AUTH_MODE")
    rule_ai_max_turns: int = Field(default=30, alias="RULE_AI_MAX_TURNS")
    rule_ai_max_budget_usd: float = Field(default=1.0, alias="RULE_AI_MAX_BUDGET_USD")
    # Our Claude is served by the ai-proxy (OpenAI/Anthropic-compatible), NOT native
    # Anthropic, in api_key mode — leave blank to hit native Anthropic directly.
    anthropic_base_url: str = Field(default="", alias="ANTHROPIC_BASE_URL")

    # --- Observability ---
    log_json: bool = True
    sentry_dsn: str = ""
    otel_exporter_otlp_endpoint: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
