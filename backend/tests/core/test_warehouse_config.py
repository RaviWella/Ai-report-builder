"""Tests for warehouse Postgres admin URL settings."""
from __future__ import annotations


def test_warehouse_admin_url_defaults_to_postgres_database(monkeypatch):
    from app.core.config import settings
    from app.core.warehouse import warehouse_admin_sync_url

    monkeypatch.setattr(
        settings,
        "WAREHOUSE_ADMIN_URL",
        "postgresql+psycopg2://warehouse_user:pass@65.108.38.187:5432/warehouse_default",
    )
    monkeypatch.setattr(settings, "WAREHOUSE_ADMIN_DATABASE", "postgres")

    assert warehouse_admin_sync_url() == (
        "postgresql+psycopg2://warehouse_user:pass@65.108.38.187:5432/postgres"
    )


def test_warehouse_admin_database_can_preserve_warehouse_default(monkeypatch):
    from app.core.config import settings
    from app.core.warehouse import warehouse_admin_sync_url

    monkeypatch.setattr(
        settings,
        "WAREHOUSE_ADMIN_URL",
        "postgresql+psycopg2://warehouse_user:pass@65.108.38.187:5432/warehouse_default",
    )
    monkeypatch.setattr(settings, "WAREHOUSE_ADMIN_DATABASE", "warehouse_default")

    assert warehouse_admin_sync_url() == (
        "postgresql+psycopg2://warehouse_user:pass@65.108.38.187:5432/warehouse_default"
    )
