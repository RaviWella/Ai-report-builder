"""Tests for Postgres URL normalization (psycopg2 migration)."""
from app.core.application_db import application_sync_url, postgres_sync_url


def test_postgres_sync_url_converts_asyncpg_driver():
    raw = "postgresql+asyncpg://user:pass@host:5432/hrm_platform?sslmode=require"
    assert postgres_sync_url(raw) == (
        "postgresql+psycopg2://user:pass@host:5432/hrm_platform?sslmode=require"
    )


def test_postgres_sync_url_preserves_psycopg2_and_sslmode():
    raw = "postgresql+psycopg2://user:pass@host:5432/db?sslmode=verify-full&sslrootcert=/ca.pem"
    assert postgres_sync_url(raw) == raw


def test_postgres_sync_url_preserves_production_psycopg2_sslmode_require():
    raw = (
        "postgresql+psycopg2://warehouse_management_user:pass@"
        "a356678-akamai-prod-6390158-default.g2a.akamaidb.net:24970/"
        "analytics-warehouse-management-pool?sslmode=require"
    )
    assert postgres_sync_url(raw) == raw


def test_application_sync_url_uses_psycopg2(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(
        settings,
        "APPLICATION_DATABASE_URL",
        "postgresql+asyncpg://u:p@localhost:5432/hrm_platform?sslmode=require",
    )
    assert "+psycopg2" in application_sync_url()
    assert "sslmode=require" in application_sync_url()
