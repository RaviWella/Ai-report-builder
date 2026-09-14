"""Datamart tests default to legacy single-schema profile (existing test fixtures).

Run with pytest (from backend/; requires pytest-sugar for progress bar):
  pytest tests/datamart
  pytest -m datamart
"""
from __future__ import annotations

import os

import pytest

# Module-level defaults before app imports (pytest loads conftest first).
os.environ["DATAMART_PROFILE"] = "legacy_audit"
os.environ["DATAMART_SCHEMA"] = "public_mint_audit"
os.environ["DATAMART_LEGACY_FALLBACK"] = "true"


def pytest_collection_modifyitems(config, items):
    """Register ``@pytest.mark.datamart`` only on tests under tests/datamart/."""
    marker = pytest.mark.datamart
    for item in items:
        nodeid = item.nodeid.replace("\\", "/")
        if "/datamart/" not in nodeid and not nodeid.startswith("datamart/"):
            continue
        item.add_marker(marker)


@pytest.fixture(autouse=True)
def _datamart_test_legacy_profile(monkeypatch, request):
    """Keep unit tests on legacy audit schema regardless of developer .env."""
    if request.node.get_closest_marker("live"):
        return
    monkeypatch.setenv("DATAMART_PROFILE", "legacy_audit")
    monkeypatch.setenv("DATAMART_SCHEMA", "public_mint_audit")
    monkeypatch.setenv("DATAMART_LEGACY_FALLBACK", "true")
