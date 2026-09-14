"""Tenant ETL defaults (no public_mint_audit as default schema)."""
from __future__ import annotations

import importlib

import app.services.ai_services.datamart.config as dm_config


def _reload_config(monkeypatch, **env: str) -> None:
    for key in (
        "DATAMART_PROFILE",
        "DATAMART_LEGACY_FALLBACK",
        "DATAMART_USE_TENANT_REGISTRY",
        "DATAMART_DB_NAME",
        "DATAMART_SCHEMA",
        "DATAMART_DEFAULT_TENANT_ID",
    ):
        monkeypatch.delenv(key, raising=False)
    for key, val in env.items():
        monkeypatch.setenv(key, val)
    importlib.reload(dm_config)


def test_default_profile_is_tenant_etl(monkeypatch):
    _reload_config(monkeypatch)
    assert dm_config.DATAMART_PROFILE == "tenant_etl"


def test_legacy_fallback_off_by_default(monkeypatch):
    _reload_config(monkeypatch)
    assert dm_config.DATAMART_LEGACY_FALLBACK is False


def test_default_warehouse_db_is_tenant_prefixed(monkeypatch):
    _reload_config(monkeypatch)
    assert dm_config.WAREHOUSE_DB == "hrm_wh_demo_tenant"


def test_query_schemas_are_hr_marts_not_legacy_audit(monkeypatch):
    _reload_config(monkeypatch)
    schemas = dm_config.parse_query_schemas()
    assert "hr" in schemas
    assert "public_mint_audit" not in schemas
