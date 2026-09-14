"""Shared helpers for Phase 10 live warehouse / API smoke tests."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from app.core.config import settings


def load_backend_dotenv() -> None:
    """Load backend/.env so DATAMART_DB_* match the smoke CLI tool."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    backend_root = Path(__file__).resolve().parents[2]
    load_dotenv(backend_root / ".env")


def live_enabled() -> bool:
    return os.getenv("DATAMART_LIVE_TEST", "").strip().lower() in ("1", "true", "yes")


def live_tenant_id() -> str:
    return (os.getenv("DATAMART_LIVE_TENANT_ID") or "demo_tenant").strip()


def live_expect_profile() -> str:
    return (os.getenv("DATAMART_LIVE_EXPECT_PROFILE") or "tenant_etl").strip().lower()


def live_smoke_url() -> str:
    return (os.getenv("DATAMART_SMOKE_URL") or "").strip().rstrip("/")


def live_api_key() -> str:
    return (os.getenv("DATAMART_SMOKE_API_KEY") or settings.API_KEY or "").strip()


def apply_real_datamart_env(monkeypatch: Any) -> None:
    """Use developer .env profile instead of unit-test legacy_audit defaults."""
    load_backend_dotenv()
    from app.services.ai_services.datamart import config as dm_config

    expect = live_expect_profile()
    if expect == "tenant_etl":
        # Phase 10 checklist: resolve via registry / hrm_wh_* probe, not legacy_audit pin.
        profile = "auto"
    else:
        profile = os.getenv("DATAMART_PROFILE", expect)
    monkeypatch.setattr(dm_config, "DATAMART_PROFILE", profile)
    monkeypatch.setattr(
        dm_config,
        "DATAMART_LEGACY_FALLBACK",
        os.getenv("DATAMART_LEGACY_FALLBACK", "true").strip().lower()
        in ("1", "true", "yes"),
    )
    monkeypatch.setattr(
        dm_config,
        "DATAMART_USE_TENANT_REGISTRY",
        os.getenv("DATAMART_USE_TENANT_REGISTRY", "false").strip().lower()
        in ("1", "true", "yes"),
    )
    if os.getenv("DATAMART_SCHEMA"):
        monkeypatch.setattr(dm_config, "WAREHOUSE_SCHEMA", os.getenv("DATAMART_SCHEMA"))
    if os.getenv("DATAMART_QUERY_SCHEMAS"):
        monkeypatch.setattr(dm_config, "DATAMART_QUERY_SCHEMAS", os.getenv("DATAMART_QUERY_SCHEMAS"))

    host = os.getenv("DATAMART_DB_HOST", dm_config.WAREHOUSE_HOST)
    port = os.getenv("DATAMART_DB_PORT", dm_config.WAREHOUSE_PORT)
    db = os.getenv("DATAMART_DB_NAME", dm_config.WAREHOUSE_DB)
    user = os.getenv("DATAMART_DB_USER", dm_config.WAREHOUSE_USER)
    password = os.getenv("DATAMART_DB_PASSWORD", dm_config.WAREHOUSE_PASSWORD)
    monkeypatch.setattr(dm_config, "WAREHOUSE_HOST", host)
    monkeypatch.setattr(dm_config, "WAREHOUSE_PORT", port)
    monkeypatch.setattr(dm_config, "WAREHOUSE_DB", db)
    monkeypatch.setattr(dm_config, "WAREHOUSE_USER", user)
    monkeypatch.setattr(dm_config, "WAREHOUSE_PASSWORD", password)
    monkeypatch.setattr(
        dm_config,
        "WAREHOUSE_DATABASE_URL",
        f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}",
    )
