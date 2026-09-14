"""MintHRM — application settings (mirrors mint-analytics config pattern)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve backend/.env regardless of process cwd (uvicorn may start from repo root).
_BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    # Application
    APP_NAME: str = "MintHRM Intelligence Platform"
    DEBUG: bool = True

    # API Key — match frontend REACT_APP_API_KEY and backend/.env.example for local dev
    API_KEY: str = "hrm-dev-api-key"

    # JWT
    SECRET_KEY: str = "hrm-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # HRIS (MinHRM PHP) launch — same base64 AES key as PHP self::$secretKey
    HRIS_LAUNCH_SECRET_KEY: str = ""
    # Optional comma-separated previous keys during PHP rotation (newest first).
    HRIS_LAUNCH_SECRET_KEYS: str = ""
    HRIS_LAUNCH_MAX_AGE_SEC: int = 300
    HRIS_LAUNCH_CLOCK_SKEW_SEC: int = 30
    HRIS_WAREHOUSE_PERMISSION: str = "warehouse_access"
    # When true, first HRIS launch auto-creates minimal tenant_registry row from subdomain.
    HRIS_LAUNCH_AUTO_PROVISION_TENANT: bool = False

    # Application Postgres — tenant registry, ETL sources, platform config (schema hrm_control).
    # Prefer APPLICATION_DATABASE_URL; otherwise DATABASE_URL / PLATFORM_DATABASE_URL with APP_DATABASE_NAME.
    APPLICATION_DATABASE_URL: str = ""
    PLATFORM_DATABASE_URL: str = ""
    DATABASE_URL: str = "postgresql+psycopg2://postgres:postgres@localhost:5433/hrm_platform"
    APP_DATABASE_NAME: str = "hrm_platform"
    # False in production: DBA creates hrm_platform once; app only connects via APPLICATION_DATABASE_URL.
    APP_AUTO_PROVISION: bool = False

    # Alembic — application DB (hrm_control.*) only; warehouse DDL is separate (runtime).
    # Docker/CI: migrations run in docker-entrypoint.sh (RUN_MIGRATIONS_IN_ENTRYPOINT, default true).
    # Local uvicorn without Docker: set RUN_MIGRATIONS_ON_STARTUP=true below.
    # Production Docker: keep RUN_MIGRATIONS_ON_STARTUP=false (entrypoint exports false after migrate).
    RUN_MIGRATIONS_ON_STARTUP: bool = True
    # When true, API lifespan exits if alembic upgrade head fails (recommended in production).
    MIGRATION_FAIL_FAST: bool = False
    # Max seconds to wait for the Postgres migration advisory lock (local --reload safety).
    MIGRATION_LOCK_TIMEOUT_SEC: int = 45
    # App-server admin URL — only used when APP_AUTO_PROVISION=true (CREATE DATABASE hrm_platform).
    POSTGRES_ADMIN_URL: str = ""

    # One warehouse Postgres database per tenant (schemas hr_raw, hr, hr_semantic, hr_control).
    # Production: warehouse cluster is usually a DIFFERENT host from APPLICATION_DATABASE_URL.
    WAREHOUSE_DEFAULT_ISOLATION: str = "database"  # database | schema
    WAREHOUSE_DB_PREFIX: str = "hrm_wh_"
    WAREHOUSE_AUTO_PROVISION: bool = True
    # Admin URL on the warehouse Postgres server (CREATE DATABASE). Falls back to POSTGRES_ADMIN_URL
    # only when WAREHOUSE_DEFAULT_HOST is unset (local dev, same server).
    WAREHOUSE_ADMIN_URL: str = ""
    # Database name on the warehouse server for CREATE DATABASE (must exist; usually postgres).
    WAREHOUSE_ADMIN_DATABASE: str = "postgres"
    # Default warehouse connection when tenant_registry.warehouse_* columns are NULL.
    WAREHOUSE_DEFAULT_HOST: str = ""
    WAREHOUSE_DEFAULT_PORT: int = 5432
    WAREHOUSE_DEFAULT_USER: str = ""
    WAREHOUSE_DEFAULT_PASSWORD: str = ""

    @property
    def application_database_url(self) -> str:
        """Canonical URL for the application / control-plane database."""
        from app.core.application_db import connection_parts, with_database

        if self.APPLICATION_DATABASE_URL:
            return self.APPLICATION_DATABASE_URL
        base = self.PLATFORM_DATABASE_URL or self.DATABASE_URL
        app_name = (self.APP_DATABASE_NAME or "hrm_platform").strip()
        parts = connection_parts(base)
        if parts["database"] == app_name:
            return base
        return with_database(base, app_name)

    @property
    def platform_database_url(self) -> str:
        """Alias for application_database_url (control plane)."""
        return self.application_database_url

    # Fernet key for encrypting MySQL passwords in tenant_registry
    DB_ENCRYPTION_KEY: str = ""

    # ETL extractor profile: "generic" (default) | "minthrm" (LinHR / MintHRM tables)
    SYNC_DATA_DICTIONARY_ON_ETL: bool = True
    MYSQL_EXTRACTOR_PROFILE: str = "generic"

    # MySQL extract tuning — keyset chunks avoid SSCursor net_write_timeout drops.
    ETL_MYSQL_CHUNK_SIZE: int = 10_000
    ETL_PG_BATCH_SIZE: int = 2_000
    ETL_MYSQL_CONNECT_TIMEOUT_SEC: int = 30
    ETL_MYSQL_READ_TIMEOUT_SEC: int = 3600
    ETL_MYSQL_WRITE_TIMEOUT_SEC: int = 3600
    ETL_MYSQL_SESSION_INIT: str = (
        "SET SESSION net_read_timeout=3600, net_write_timeout=3600, wait_timeout=28800"
    )
    ETL_EXTRACT_MAX_RETRIES: int = 3
    ETL_EXTRACT_RETRY_BASE_SEC: float = 2.0

    # Source schema mapping (YAML under hr_etl/mappings/). Variant defaults to SOURCE_TYPE.
    SOURCE_MAPPING_PROFILE: str = ""
    SOURCE_MAPPING_VARIANT: str = ""

    # Source DB defaults for scripts/register_tenant.py (never commit real passwords)
    # SOURCE_* override MYSQL_* when set; source_type: mysql | postgres
    SOURCE_TYPE: str = ""
    SOURCE_HOST: str = ""
    SOURCE_PORT: int = 0
    SOURCE_DB: str = ""
    SOURCE_USER: str = ""
    SOURCE_PASSWORD: str = ""
    MYSQL_HOST: str = ""
    MYSQL_PORT: int = 3306
    MYSQL_DB: str = ""
    MYSQL_USER: str = ""
    MYSQL_PASSWORD: str = ""
    MYSQL_TENANT_ID: str = "demo_tenant"

    @property
    def etl_source_type(self) -> str:
        return (self.SOURCE_TYPE or "mysql").strip().lower()

    @property
    def etl_source_host(self) -> str:
        return self.SOURCE_HOST or self.MYSQL_HOST

    @property
    def etl_source_port(self) -> int:
        if self.SOURCE_PORT:
            return self.SOURCE_PORT
        if self.etl_source_type == "postgres":
            return 5432
        return self.MYSQL_PORT

    @property
    def etl_source_db(self) -> str:
        return self.SOURCE_DB or self.MYSQL_DB

    @property
    def etl_source_user(self) -> str:
        return self.SOURCE_USER or self.MYSQL_USER

    @property
    def etl_source_password(self) -> str:
        return self.SOURCE_PASSWORD or self.MYSQL_PASSWORD

    # AI Backend — Minchy proxy or local Ollama
    EXPERIENCE_LLM_BACKEND: str = "ollama"          # "ollama" | "minchy"
    OLLAMA_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5:7b"
    OLLAMA_AUTH: str = ""  # Base64 Basic credentials for hosted ai-core.minchy.ai
    OLLAMA_NUM_CTX: int = 65536
    EXPERIENCE_LLM_MODEL: str = "qwen2.5:7b"
    EXPERIENCE_LLM_USER: str = "mint-hrm-dev"

    # Minchy AI proxy
    MINCHY_AI_BASE_URL: str = "https://ai-proxy.minchy.ai"
    MINCHY_AI_API_KEY: str = ""
    MINCHY_AI_MODEL: str = "qwen3.5-128k"

    # Alias used by the datamart text-to-SQL agent (falls back to MINCHY_AI_API_KEY).
    AI_PROXY_API_KEY: str = ""

    # Claude interpreter (optional)
    INTERPRETER_PROVIDER: str = "off"               # "off" | "claude"
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_INTERPRETER_MODEL: str = "claude-haiku-4-5"
    ANTHROPIC_API_BASE: str = "https://api.anthropic.com"

    # Embedding
    EMBEDDING_MODEL: str = "nomic-embed-text:latest"
    RETRIEVAL_TOP_K: int = 15

    # CORS
    CORS_ORIGINS: str = '["http://localhost:5174","http://localhost:5173","http://localhost:3001"]'

    @property
    def cors_origins_list(self) -> List[str]:
        return json.loads(self.CORS_ORIGINS)


settings = Settings()
