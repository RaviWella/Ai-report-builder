"""DataHub fast-path when GMS is not configured for local dev."""
from __future__ import annotations

from app.services.ai_services.datamart import datahub


def test_search_skips_localhost_without_token(monkeypatch):
    monkeypatch.setenv("DATAMART_USE_DATAHUB", "auto")
    monkeypatch.setenv("DATAHUB_GMS_URL", "http://localhost:8080")
    monkeypatch.setenv("DATAHUB_GMS_TOKEN", "")
    datahub._DATAHUB_CIRCUIT_OPEN_UNTIL = 0.0
    assert datahub.search_relevant_tables("payroll summary by employee") == []


def test_search_honours_explicit_enable(monkeypatch):
    monkeypatch.setenv("DATAMART_USE_DATAHUB", "true")
    monkeypatch.setenv("DATAHUB_GMS_URL", "http://localhost:8080")
    datahub._DATAHUB_CIRCUIT_OPEN_UNTIL = 0.0
    # Should attempt network (may return [] on connection error) — not skip at gate.
    assert datahub._datahub_explicitly_enabled() is True
