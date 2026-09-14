"""The tenant key becomes a physical database name (mint_<key>) and is request-
adjacent, so it must be validated before interpolation — reject anything that
isn't a warehouse tenant_code, and never let it name a non-tenant database.

HRIS JWT tenant_id is the host label (coca-cola, hris.coca-cola). Those fold
to identifier-safe warehouse keys; they are not rejected.
"""

import pytest

from app.db.datamart import _datamart_url_for, _safe_datamart_key
from app.repositories.tenant_provision import default_datamart_key


@pytest.mark.parametrize("key,expected", [
    ("sejaya", "sejaya"),
    ("brandix_apparel", "brandix_apparel"),
    ("jjm", "jjm"),
    ("t1", "t1"),
    ("demo_tenant", "demo_tenant"),
    ("coca-cola", "coca_cola"),
    ("hris.coca-cola", "hris_coca_cola"),
    ("Sejaya", "sejaya"),
    ("lk-minthrm", "lk_minthrm"),
])
def test_valid_keys_pass(key, expected):
    assert _safe_datamart_key(key) == expected


@pytest.mark.parametrize("key", [
    "a b",           # space
    'x"; DROP',      # injection-ish
    "1abc",          # must start with a letter
    "",              # empty
    "control",       # would target the control-plane DB (mint_control)
    "postgres",      # reserved
    "template1",     # reserved
])
def test_unsafe_keys_rejected(key):
    with pytest.raises(ValueError):
        _safe_datamart_key(key)


def test_url_builds_mint_db_for_valid_key():
    assert "mint_sejaya" in _datamart_url_for("sejaya")


def test_url_folds_hris_host_label_to_warehouse_db():
    assert "mint_coca_cola" in _datamart_url_for("coca-cola")


def test_url_rejects_reserved_key():
    with pytest.raises(ValueError):
        _datamart_url_for("control")


def test_default_datamart_key_folds_hyphenated_hris_subdomain():
    assert default_datamart_key("coca-cola") == "coca_cola"
    assert default_datamart_key("hris.coca-cola") == "hris_coca_cola"
