"""WS-1 — run lineage: result_checksum + compiled_sql_hash properties."""

from __future__ import annotations

from app.domain.report_spec import DataSpec
from app.query_engine.compiler import compile_query
from app.query_engine.runner import _sha256, render_sql, result_checksum
from app.services.semantic_seed import build_seed_catalog


def test_result_checksum_is_order_independent():
    cols = ["a", "b"]
    rows = [{"a": 1, "b": 2}, {"a": 3, "b": 4}]
    reordered = [{"a": 3, "b": 4}, {"a": 1, "b": 2}]
    assert result_checksum(cols, rows) == result_checksum(cols, reordered)


def test_result_checksum_moves_on_any_change():
    cols = ["a", "b"]
    base = [{"a": 1, "b": 2}, {"a": 3, "b": 4}]
    changed_value = [{"a": 1, "b": 2}, {"a": 3, "b": 5}]
    assert result_checksum(cols, base) != result_checksum(cols, changed_value)
    # a column rename changes it
    assert result_checksum(["a", "b"], base) != result_checksum(["a", "x"], base)
    # an extra row changes it
    assert result_checksum(cols, base) != result_checksum(cols, base + [{"a": 9, "b": 9}])


def test_result_checksum_stable_and_handles_nulls():
    cols = ["a", "b"]
    rows = [{"a": None, "b": 2}, {"a": 1, "b": None}]
    assert result_checksum(cols, rows) == result_checksum(cols, list(rows))
    assert result_checksum(cols, []) == result_checksum(cols, [])  # empty is stable


def test_compiled_sql_hash_is_deterministic_and_spec_sensitive():
    cat = build_seed_catalog("t", 1)
    spec = DataSpec.model_validate({"entity": "employee", "fields": [{"ref": "employee.full_name"}]})
    h1 = _sha256(render_sql(compile_query(spec, cat, {})))
    h2 = _sha256(render_sql(compile_query(spec, cat, {})))
    assert h1 == h2  # same spec + catalogue → identical hash
    other = DataSpec.model_validate({"entity": "employee", "fields": [{"ref": "employee.department"}]})
    assert h1 != _sha256(render_sql(compile_query(other, cat, {})))  # different spec → different hash
