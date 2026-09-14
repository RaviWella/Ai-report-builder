"""
Datamart configuration — backward-compatible exports.

Prefer ``settings.SETTINGS`` for new code. Legacy modules import names from here.
"""
from __future__ import annotations

from app.core.config import settings

from .settings import SETTINGS, DatamartSettings, load_settings

# ── Warehouse ───────────────────────────────────────────────────
WAREHOUSE_HOST = SETTINGS.warehouse_host
WAREHOUSE_PORT = SETTINGS.warehouse_port
WAREHOUSE_USER = SETTINGS.warehouse_user
WAREHOUSE_PASSWORD = SETTINGS.warehouse_password
WAREHOUSE_DB = SETTINGS.warehouse_db
DATAMART_DEFAULT_TENANT_ID = SETTINGS.default_tenant_id
DATAMART_DEFAULT_USER_ID = SETTINGS.default_user_id
DATAMART_REQUIRE_TENANT_HEADER = SETTINGS.require_tenant_header
DATAMART_PROFILE = SETTINGS.profile
DATAMART_QUERY_SCHEMAS = SETTINGS.query_schemas
DATAMART_PRIMARY_SCHEMA = SETTINGS.primary_schema
DATAMART_LEGACY_FALLBACK = SETTINGS.legacy_fallback
DATAMART_METADATA_CACHE_TTL_SEC = SETTINGS.metadata_cache_ttl_sec
DATAMART_USE_TENANT_REGISTRY = SETTINGS.use_tenant_registry
DATAMART_PREFER_TENANT_REGISTRY = SETTINGS.prefer_tenant_registry

WAREHOUSE_DATABASE_URL = (
    f"postgresql+psycopg2://{WAREHOUSE_USER}:{WAREHOUSE_PASSWORD}"
    f"@{WAREHOUSE_HOST}:{WAREHOUSE_PORT}/{WAREHOUSE_DB}"
)

WAREHOUSE_SCHEMA = __import__("os").getenv("DATAMART_SCHEMA", "")

# ── DataHub ───────────────────────────────────────────────────────
DATAHUB_GMS_URL = SETTINGS.datahub_gms_url
DATAHUB_GMS_TOKEN = SETTINGS.datahub_gms_token
DATAHUB_TIMEOUT_SECONDS = SETTINGS.datahub_timeout_sec
DATAMART_USE_DATAHUB = SETTINGS.use_datahub
DATAMART_TABLE_LIST_CACHE_TTL_SEC = SETTINGS.table_list_cache_ttl_sec

# ── LLM ───────────────────────────────────────────────────────────
AI_PROXY_MODEL = SETTINGS.chat_model
DATAMART_CHAT_MODEL = SETTINGS.chat_model
DATAMART_TEMPLATE_MODEL = SETTINGS.template_model
DATAMART_REPAIR_MODEL = SETTINGS.repair_model
AI_PROXY_BASE_URL = getattr(settings, "MINCHY_AI_BASE_URL", "https://ai-proxy.minchy.ai")
AI_PROXY_API_KEY = getattr(settings, "AI_PROXY_API_KEY", "") or getattr(
    settings, "MINCHY_AI_API_KEY", ""
)
AI_PROXY_USER = getattr(settings, "EXPERIENCE_LLM_USER", "mint-hrm-dev")

LLM_CONTEXT_TOKEN_LIMIT = SETTINGS.llm_context_tokens
LLM_COMPLETION_RESERVE_TOKENS = SETTINGS.llm_completion_reserve
LLM_INPUT_TOKEN_BUDGET = LLM_CONTEXT_TOKEN_LIMIT - LLM_COMPLETION_RESERVE_TOKENS
CHARS_PER_TOKEN_EST = SETTINGS.chars_per_token
MAX_SQL_RETRIES = SETTINGS.max_sql_retries
WAREHOUSE_CONNECT_TIMEOUT_SEC = SETTINGS.warehouse_connect_timeout_sec
WAREHOUSE_STATEMENT_TIMEOUT_SEC = SETTINGS.warehouse_statement_timeout_sec

# ── Results / broker ──────────────────────────────────────────────
MAX_RESULT_ROWS = SETTINGS.max_result_rows
POST_PROCESS_APPEND_HEADROOM = 120
MAX_DATAMART_OUTPUT_ROWS = MAX_RESULT_ROWS + POST_PROCESS_APPEND_HEADROOM

SEARCH_STOP_WORDS = frozenset({
    "show", "me", "the", "top", "and", "their", "with", "of", "in",
    "for", "a", "an", "is", "are", "what", "who", "how", "many",
    "all", "by", "from", "to", "get", "give", "list", "find",
    "highest", "lowest", "most", "least", "best", "worst",
    "details", "information", "data", "records", "entries",
    "please", "can", "you", "tell", "about", "want",
})
MAX_SEARCH_KEYWORDS = 5
MAX_CONTEXT_TABLES = 12
BROKER_MAX_TABLES = SETTINGS.broker_max_tables
BROKER_MAX_TABLES_TOPIC = SETTINGS.broker_max_tables_topic
BROKER_MAX_COLUMNS_PER_TABLE = 120
BROKER_MAX_PROMPT_CHARS = 4_500

CHAT_HISTORY_MAX_CHARS = 4_000
CHAT_REFINEMENT_ANCHOR_SQL_MAX_CHARS = 9_000
TEMPLATE_SCHEMA_MAX_CHARS = 5_000
TEMPLATE_SQL_MAX_CHARS = 6_000
TEMPLATE_POST_PROCESS_JSON_MAX_CHARS = 2_500

# ── Pipeline (fixed defaults; only critical gates are env-tunable) ─
DATAMART_VALIDATION_ENABLED = True
DATAMART_VALIDATION_ENFORCE_RETRIEVAL = False
DATAMART_VALIDATION_FAITHFULNESS = True
DATAMART_VALIDATION_CRITIC = False
DATAMART_VALIDATION_RELEVANCE_FILTER = True
DATAMART_VALIDATION_STRICT_BINDING = False
DATAMART_BINDING_EXPAND_FROM_SQL = False
DATAMART_VALIDATION_VERIFIED_METRICS = True
DATAMART_VALIDATION_BLOCK_INSUFFICIENT_EXEC = SETTINGS.block_on_insufficient_retrieval
DATAMART_VALIDATION_REQUIRE_ADEQUACY = SETTINGS.require_sql_adequacy
DATAMART_MAX_REPAIR_ATTEMPTS_PER_TURN = SETTINGS.max_repair_attempts_per_turn
DATAMART_CHAT_CLARIFY_ON_AMBIGUOUS = SETTINGS.clarify_on_ambiguous
DATAMART_CHAT_CLARIFICATION_UI = SETTINGS.clarification_ui
DATAMART_LOG_LLM_CONTEXT = SETTINGS.log_llm_context
DATAMART_LOG_LLM_CONTEXT_MAX_CHARS = SETTINGS.debug_log_llm_context_max_chars
DATAMART_PREFER_DETERMINISTIC_SQL = SETTINGS.prefer_deterministic_sql
DATAMART_SCHEMA_CATALOG_FIRST = SETTINGS.schema_catalog_first
DATAMART_REPORT_SPEC_ENABLED = SETTINGS.report_spec_enabled
DATAMART_TIER_C_QUERY_PLAN = SETTINGS.tier_c_query_plan
DATAMART_TIER_C_SLIM_PROMPT = SETTINGS.tier_c_slim_prompt
DATAMART_BLOCK_STUB_SQL = SETTINGS.block_stub_sql
DATAMART_VERIFIED_MIN_SCORE = SETTINGS.verified_min_score
DATAMART_FAST_PATH_SKIP_AMBIGUOUS_BLOCK = True
DATAMART_FAST_PATH_LIGHT_VALIDATION = True

# Removed experimental flags — always validate in production pipeline
DATAMART_NON_VALIDATION_CHECK = False

SAMPLE_QUESTIONS: list[str] = [
    "Show me the top 10 highest paid employees and their job titles",
    "How many employees joined in the last 6 months?",
    "What is the average salary by department?",
    "List employees who are currently on leave",
    "Show attendance summary for this month",
    "Which departments have the highest attrition rate?",
]


def parse_query_schemas() -> tuple[str, ...]:
    raw = (DATAMART_QUERY_SCHEMAS or "hr_semantic,hr,hr_snap").strip()
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    return tuple(parts) if parts else ("hr_semantic", "hr", "hr_snap")


def primary_schema_name() -> str:
    primary = (DATAMART_PRIMARY_SCHEMA or "hr_semantic").strip()
    schemas = parse_query_schemas()
    return primary if primary in schemas else schemas[0]


def allowed_schemas_lower_static() -> frozenset[str]:
    return frozenset(s.lower() for s in parse_query_schemas())
