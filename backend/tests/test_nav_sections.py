"""Unit tests for per-tenant Report Builder nav section flags."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.repositories.tenant_provision import (
    DEFAULT_NAV_SECTION_FLAGS,
    DEFAULT_NAV_SECTIONS,
    enabled_nav_sections,
    normalize_nav_sections,
    get_nav_sections,
    set_nav_sections,
)


def test_normalize_null_uses_default_flags():
    assert normalize_nav_sections(None) == DEFAULT_NAV_SECTION_FLAGS
    assert normalize_nav_sections({}) == DEFAULT_NAV_SECTION_FLAGS
    assert "Config" not in DEFAULT_NAV_SECTION_FLAGS
    assert "AI Settings" not in DEFAULT_NAV_SECTION_FLAGS


def test_normalize_boolean_map():
    raw = {
        "Chat": True,
        "Builder": False,
        "Documents": True,
        "Viewer": True,
        "How it works": False,
    }
    assert normalize_nav_sections(raw) == raw


def test_normalize_drops_admin_only_keys():
    out = normalize_nav_sections(
        {
            "Chat": True,
            "Config": True,
            "AI Settings": True,
            "Documents": True,
            "Viewer": True,
            "Builder": False,
            "How it works": False,
        }
    )
    assert "Config" not in out
    assert "AI Settings" not in out
    assert out["Chat"] is True


def test_normalize_legacy_allow_list():
    assert normalize_nav_sections({"sections": ["Chat", "Builder"]}) == {
        "Chat": True,
        "Builder": True,
        "Documents": False,
        "Viewer": False,
        "How it works": False,
    }


def test_enabled_nav_sections_includes_templates():
    flags = normalize_nav_sections({"sections": ["Documents", "Viewer"]})
    assert enabled_nav_sections(flags) == DEFAULT_NAV_SECTIONS


def test_get_nav_sections_defaults_when_no_row():
    class EmptySession:
        def get(self, *_args, **_kwargs):
            return None

    assert get_nav_sections(EmptySession(), "acme") == DEFAULT_NAV_SECTION_FLAGS


def test_set_nav_sections_stores_grantable_only():
    row = SimpleNamespace(nav_sections=None, status="active")

    class Session:
        def get(self, _model, key):
            return row if key == "acme" else None

        def flush(self):
            return None

    set_nav_sections(
        Session(),
        "acme",
        {
            "Chat": True,
            "Builder": True,
            "Documents": True,
            "Viewer": True,
            "How it works": False,
        },
    )
    assert row.nav_sections["Chat"] is True
    assert "Config" not in row.nav_sections


def test_set_nav_sections_rejects_unknown():
    row = SimpleNamespace(nav_sections=None, status="active")

    class Session:
        def get(self, _model, key):
            return row if key == "acme" else None

        def flush(self):
            return None

    with pytest.raises(ValueError, match="Unknown nav sections"):
        set_nav_sections(Session(), "acme", {"Chat": True, "NotASection": True})


def test_set_nav_sections_requires_provisioned_tenant():
    class Session:
        def get(self, *_args, **_kwargs):
            return None

    with pytest.raises(LookupError, match="not provisioned"):
        set_nav_sections(Session(), "missing", {"Chat": True})
