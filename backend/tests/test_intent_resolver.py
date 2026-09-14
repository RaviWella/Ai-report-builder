"""WS-2 — deterministic NL → spec: common requests resolve with zero LLM calls."""

from __future__ import annotations

import types

import pytest

from app.core.tenancy import TenantContext
from app.domain.enums import AggFn, Role
from app.domain.semantic import MetricDef
from app.query_engine import guards
from app.services.ai_service import AIService
from app.services.intent_resolver import resolve_intent
from app.services.semantic_seed import build_seed_catalog


@pytest.fixture
def catalog():
    return build_seed_catalog("t", 1)


@pytest.fixture
def metric_catalog():
    cat = build_seed_catalog("t", 1)
    cat.metrics = [
        MetricDef(key="headcount", label="Headcount", kind="count", ref="employee.emp_no",
                  distinct=True, aliases=["staff count", "number of employees"]),
        MetricDef(key="total_net", label="Total Net Pay", kind="aggregate", agg=AggFn.SUM,
                  ref="payroll.net", aliases=["net pay", "total take home"]),
    ]
    return cat


@pytest.mark.parametrize(
    "request_text, expect_grouped",
    [
        ("Total Basic Salary by Department", True),
        ("average basic salary by department", True),
        ("headcount by department", True),
        ("Employee Name, Department and Basic Salary", False),
        ("Net Salary by Designation", False),  # no aggregation word → field list, not a roll-up
    ],
)
def test_common_requests_resolve_to_valid_specs(catalog, request_text, expect_grouped):
    resolved = resolve_intent(request_text, catalog)
    assert resolved is not None, request_text
    assert resolved.confidence >= 0.6
    spec = resolved.data_spec
    # Every deterministic spec must pass the same guards as an LLM spec.
    guards.validate_refs(spec, catalog)
    guards.validate_joins(spec, catalog)
    assert bool(spec.group_by) == expect_grouped
    if expect_grouped:
        assert spec.aggregations


def test_metric_label_resolves_to_governed_ref(metric_catalog):
    """A named metric resolves to metric.<key> — the one governed definition —
    instead of being re-derived as a raw count/sum."""
    resolved = resolve_intent("headcount by department", metric_catalog)
    assert resolved is not None
    assert resolved.confidence >= 0.6
    spec = resolved.data_spec
    refs = [f.ref for f in spec.fields]
    assert "metric.headcount" in refs
    assert "employee.department" in refs
    # The metric claimed "headcount", so no raw count aggregation was re-derived.
    assert not spec.aggregations
    guards.validate_refs(spec, metric_catalog)
    guards.validate_joins(spec, metric_catalog)


def test_metric_alias_resolves(metric_catalog):
    resolved = resolve_intent("total net pay by department", metric_catalog)
    assert resolved is not None
    refs = [f.ref for f in resolved.data_spec.fields]
    assert "metric.total_net" in refs
    assert "employee.department" in refs


def test_bare_metric_without_dimension(metric_catalog):
    resolved = resolve_intent("show me total net pay", metric_catalog)
    assert resolved is not None
    assert [f.ref for f in resolved.data_spec.fields] == ["metric.total_net"]
    guards.validate_refs(resolved.data_spec, metric_catalog)


def test_metric_wins_over_field_rederivation(metric_catalog):
    """'Headcount' must hit the governed metric, never a re-derived count agg."""
    resolved = resolve_intent("headcount", metric_catalog)
    assert resolved is not None
    assert [f.ref for f in resolved.data_spec.fields] == ["metric.headcount"]
    assert not resolved.data_spec.aggregations


def test_unmatched_request_returns_none(catalog):
    assert resolve_intent("show me the weather tomorrow", catalog) is None


def test_from_natural_language_serves_deterministic_without_calling_the_llm(catalog):
    """The acceptance property: a common request is served by the deterministic
    path and the LLM provider is never invoked."""
    svc = AIService.__new__(AIService)  # bypass __init__ (no DB needed)
    svc.semantic = types.SimpleNamespace(get_active_catalog=lambda _tid: catalog)
    svc.audit = types.SimpleNamespace(log=lambda **_k: None)

    def _boom(*_a, **_k):
        raise AssertionError("LLM provider must not be called for a common request")

    svc._provider = _boom

    ctx = TenantContext(tenant_id="t", pg_schema="t", acting_user_id="u", role=Role.SUPPORT_ADMIN, on_behalf=False)
    proposal = svc.from_natural_language(ctx, "Total Basic Salary by Department")
    assert proposal.source == "deterministic"
    assert proposal.data_spec.group_by == ["employee.department"]
