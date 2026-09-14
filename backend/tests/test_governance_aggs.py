"""G1 — allowed_aggregations governance tests (no DB required).

OFF by default → no behaviour change. ON → a value-aggregation must be declared on
the field; COUNT/COUNT DISTINCT are always allowed.

Seed fixtures used:
  - payroll.basic        → _MONEY = SUM/AVG/MIN/MAX  (SUM allowed)
  - employee.tenure_years→ AVG/MIN/MAX only          (SUM NOT allowed)
  - employee.full_name   → dimension, no aggs        (COUNT allowed, SUM not)
"""

from __future__ import annotations

import pytest

from app.domain.report_spec import DataSpec
from app.query_engine import guards
from app.query_engine.compiler import compile_query
from app.services.semantic_seed import build_seed_catalog


@pytest.fixture
def catalog():
    return build_seed_catalog("tenant_test", 1)


@pytest.fixture
def enforce(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "query_enforce_allowed_aggregations", True, raising=False)


def _agg_spec(ref: str, fn: str):
    return DataSpec.model_validate(
        {"entity": "employee", "aggregations": [{"ref": ref, "fn": fn, "label": "x"}]}
    )


def test_off_by_default_allows_any_aggregation(catalog):
    # default config: disallowed SUM on tenure_years compiles fine (no enforcement)
    compile_query(_agg_spec("employee.tenure_years", "sum"), catalog, {})


def test_on_allows_declared_aggregation(catalog, enforce):
    compile_query(_agg_spec("payroll.basic", "sum"), catalog, {})  # SUM ∈ _MONEY


def test_on_rejects_undeclared_aggregation(catalog, enforce):
    # tenure_years allows AVG/MIN/MAX but NOT SUM
    with pytest.raises(guards.GuardError):
        compile_query(_agg_spec("employee.tenure_years", "sum"), catalog, {})


def test_on_allows_other_declared_aggregation(catalog, enforce):
    compile_query(_agg_spec("employee.tenure_years", "avg"), catalog, {})  # AVG allowed


def test_on_count_always_allowed_even_on_dimension(catalog, enforce):
    # counting a dimension (no value-aggs declared) is always valid
    compile_query(_agg_spec("employee.full_name", "count"), catalog, {})


def test_on_rejects_value_agg_on_dimension(catalog, enforce):
    with pytest.raises(guards.GuardError):
        compile_query(_agg_spec("employee.full_name", "sum"), catalog, {})


def test_on_enforces_field_selection_agg_too(catalog, enforce):
    # the same guard applies to a FieldSelection-level agg, not just aggregations[]
    spec = DataSpec.model_validate(
        {"entity": "employee",
         "fields": [{"ref": "employee.tenure_years", "agg": "sum", "label": "x"}]}
    )
    with pytest.raises(guards.GuardError):
        compile_query(spec, catalog, {})
