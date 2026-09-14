"""EXPLAIN construct + L6 cost governor tests (no DB required).

Locks the safety-critical invariants: EXPLAIN never runs ANALYZE by default, the
plan parser is tolerant, and the cost guard is OFF unless explicitly configured.
"""

from __future__ import annotations

import pytest
from sqlalchemy.dialects import postgresql

from app.domain.report_spec import DataSpec
from app.query_engine import guards, runner
from app.query_engine.compiler import compile_query
from app.query_engine.explain import (
    Explain,
    estimated_cost,
    estimated_rows,
    explain_plan,
    top_plan,
)
from app.services.semantic_seed import build_seed_catalog


@pytest.fixture
def catalog():
    return build_seed_catalog("tenant_test", 1)


def _stmt(catalog):
    spec = DataSpec.model_validate(
        {"entity": "employee", "fields": [{"ref": "employee.emp_no"}]}
    )
    return compile_query(spec, catalog, {}).statement


def _sql(stmt) -> str:
    return str(stmt.compile(dialect=postgresql.dialect()))


def test_explain_wraps_select_and_never_analyzes_by_default(catalog):
    sql = _sql(Explain(_stmt(catalog)))
    assert sql.startswith("EXPLAIN (FORMAT JSON) ")
    assert "ANALYZE" not in sql.upper()
    # the inner statement is still a plain SELECT (the query, untouched)
    assert "SELECT" in sql


def test_explain_analyze_is_opt_in(catalog):
    sql = _sql(Explain(_stmt(catalog), analyze=True))
    assert "ANALYZE" in sql.upper()


_SAMPLE_PLAN = [{"Plan": {"Node Type": "Seq Scan", "Total Cost": 12345.6, "Plan Rows": 9876}}]


def test_plan_parsers():
    assert top_plan(_SAMPLE_PLAN)["Node Type"] == "Seq Scan"
    assert estimated_cost(_SAMPLE_PLAN) == 12345.6
    assert estimated_rows(_SAMPLE_PLAN) == 9876
    # tolerant of the raw-string form psycopg may hand back
    import json

    assert estimated_cost(json.dumps(_SAMPLE_PLAN)) == 12345.6
    # unexpected shapes → None / {}, never an exception
    assert estimated_cost(None) is None
    assert estimated_rows("not json") is None
    assert top_plan({}) == {}


class _FakeResult:
    def __init__(self, plan):
        self._plan = plan

    def scalar(self):
        return self._plan


class _FakeConn:
    def __init__(self, plan):
        self._plan = plan
        self.executed = False

    def execute(self, _stmt):
        self.executed = True
        return _FakeResult(self._plan)


def test_explain_plan_shape():
    conn = _FakeConn(_SAMPLE_PLAN)
    out = explain_plan(conn, "SELECT 1")
    assert out["total_cost"] == 12345.6 and out["est_rows"] == 9876
    assert conn.executed


def test_cost_guard_off_by_default(catalog, monkeypatch):
    from app.core.config import settings

    # default config: guard disabled → returns without touching the connection
    monkeypatch.setattr(settings, "query_cost_guard_enabled", False, raising=False)
    conn = _FakeConn(_SAMPLE_PLAN)
    runner._assert_within_cost_budget(conn, _stmt(catalog))
    assert not conn.executed  # never EXPLAINs when disabled


def test_cost_guard_rejects_over_threshold(catalog, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "query_cost_guard_enabled", True, raising=False)
    monkeypatch.setattr(settings, "query_max_estimated_cost", 1000.0, raising=False)
    conn = _FakeConn(_SAMPLE_PLAN)  # cost 12345.6 > 1000
    with pytest.raises(guards.GuardError):
        runner._assert_within_cost_budget(conn, _stmt(catalog))


def test_cost_guard_allows_under_threshold(catalog, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "query_cost_guard_enabled", True, raising=False)
    monkeypatch.setattr(settings, "query_max_estimated_cost", 1_000_000.0, raising=False)
    conn = _FakeConn(_SAMPLE_PLAN)  # cost 12345.6 < 1,000,000
    runner._assert_within_cost_budget(conn, _stmt(catalog))  # no raise


def test_cost_guard_never_blocks_on_explain_failure(catalog, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "query_cost_guard_enabled", True, raising=False)
    monkeypatch.setattr(settings, "query_max_estimated_cost", 1.0, raising=False)

    class _BoomConn:
        def execute(self, _stmt):
            raise RuntimeError("EXPLAIN blew up")

    # an EXPLAIN failure must degrade to allowing the run, never raise
    runner._assert_within_cost_budget(_BoomConn(), _stmt(catalog))
