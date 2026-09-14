"""Result cache — key is content-addressed by data version; (de)serialization is
exact; a missing/disabled Redis degrades to no-cache (never breaks a run)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.query_engine.runner import QueryResult
from app.services import result_cache
from app.services.result_cache import ResultCache, decode, encode, make_key


def _result():
    return QueryResult(
        columns=["dept", "net"],
        rows=[{"dept": "Eng", "net": Decimal("1234.50")}, {"dept": "Ops", "net": None}],
        sql="SELECT ...", row_count=2, truncated=False,
        compiled_sql_hash="abc", result_checksum="def",
    )


def test_key_is_stable_and_separates_on_every_part():
    base = make_key("t1", "sql1", {"year": 2026}, "snap1")
    assert base == make_key("t1", "sql1", {"year": 2026}, "snap1")  # deterministic
    assert base != make_key("t2", "sql1", {"year": 2026}, "snap1")  # tenant
    assert base != make_key("t1", "sql2", {"year": 2026}, "snap1")  # sql
    assert base != make_key("t1", "sql1", {"year": 2025}, "snap1")  # params
    assert base != make_key("t1", "sql1", {"year": 2026}, "snap2")  # snapshot -> freshness


def test_param_order_does_not_change_key():
    assert make_key("t", "s", {"a": 1, "b": 2}, "x") == make_key("t", "s", {"b": 2, "a": 1}, "x")


def test_encode_decode_is_exact_including_decimal_and_none():
    r = _result()
    back = decode(encode(r))
    assert back.columns == r.columns
    assert back.rows == r.rows  # Decimal and None preserved exactly
    assert isinstance(back.rows[0]["net"], Decimal)
    assert back.result_checksum == r.result_checksum


def test_disabled_cache_degrades_to_no_cache(monkeypatch):
    monkeypatch.setattr(result_cache.settings, "result_cache_enabled", False)
    rc = ResultCache()
    assert rc.enabled is False
    assert rc.get(make_key("t", "s", {}, "x")) is None
    assert rc.acquire("k") is True  # no lock -> everyone computes
    rc.release("k")  # no-op, must not raise
    assert rc.wait_for("k") is None
