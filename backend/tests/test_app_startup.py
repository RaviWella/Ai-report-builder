"""Regression tests for FastAPI lifespan startup."""
from __future__ import annotations

import sys
import types

import pytest


@pytest.mark.asyncio
async def test_lifespan_enters_and_runs_init_db(monkeypatch):
    from fastapi import APIRouter

    fake_migrations = types.ModuleType("app.core.migrations")
    fake_migrations.run_platform_migrations = lambda: None
    monkeypatch.setitem(sys.modules, "app.core.migrations", fake_migrations)
    fake_routes = types.ModuleType("app.api.routes")
    fake_routes.api_router = APIRouter()
    monkeypatch.setitem(sys.modules, "app.api.routes", fake_routes)
    fake_llm_client = types.ModuleType("app.services.ai_services.datamart.llm.llm_client")
    fake_llm_client.clear_llm_cache = lambda: None
    fake_llm_client.sync_process_openai_api_key = lambda: None
    monkeypatch.setitem(
        sys.modules,
        "app.services.ai_services.datamart.llm.llm_client",
        fake_llm_client,
    )
    fake_llm_settings = types.ModuleType("app.services.ai_services.datamart.llm.llm_settings")
    fake_llm_settings.log_llm_config_status = lambda: None
    fake_llm_settings.resolve_llm_connection = lambda _model: types.SimpleNamespace(
        backend="test",
        model="test-model",
        base_url="http://test.invalid",
    )
    monkeypatch.setitem(
        sys.modules,
        "app.services.ai_services.datamart.llm.llm_settings",
        fake_llm_settings,
    )

    from app import main as app_main

    calls: list[str] = []

    def fake_init_db_sync() -> None:
        calls.append("init_db_sync")

    async def fake_to_thread(func, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr(app_main.settings, "RUN_MIGRATIONS_ON_STARTUP", False)
    monkeypatch.setattr(app_main, "init_db_sync", fake_init_db_sync)
    monkeypatch.setattr(app_main.asyncio, "to_thread", fake_to_thread)
    monkeypatch.setattr(app_main, "_bootstrap_datamart_llm_env", lambda: None)
    monkeypatch.setattr(app_main, "_warn_duplicate_port_8000_listeners", lambda: None)

    async with app_main.lifespan(app_main.app):
        assert calls == ["init_db_sync"]
