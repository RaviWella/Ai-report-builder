"""Business glossary — governed terms ground the NL resolver onto governed refs."""

from __future__ import annotations

import pytest

from app.domain.enums import AggFn
from app.domain.semantic import GlossaryTerm, MetricDef
from app.services.intent_resolver import resolve_intent
from app.services.semantic_seed import build_seed_catalog


@pytest.fixture
def catalog():
    cat = build_seed_catalog("t", 1)
    cat.metrics = [
        MetricDef(key="total_net", label="Total Net Pay", kind="aggregate", agg=AggFn.SUM,
                  ref="payroll.net"),
        MetricDef(key="headcount", label="Headcount", kind="count", ref="employee.emp_no",
                  distinct=True),
    ]
    cat.glossary = [
        GlossaryTerm(term="Take-home Pay", ref="metric.total_net",
                     aliases=["in-hand salary", "net pay"],
                     definition="Net amount after all deductions."),
        GlossaryTerm(term="Staff Strength", ref="metric.headcount",
                     aliases=["manpower"], definition="Active employee count."),
    ]
    return cat


def test_glossary_synonym_resolves_to_governed_metric(catalog):
    """A glossary synonym that isn't a metric label still maps onto the metric."""
    resolved = resolve_intent("in-hand salary by department", catalog)
    assert resolved is not None
    refs = [f.ref for f in resolved.data_spec.fields]
    assert "metric.total_net" in refs
    assert "employee.department" in refs
    assert not resolved.data_spec.aggregations  # governed metric, not re-derived


def test_glossary_term_name_resolves(catalog):
    resolved = resolve_intent("show me staff strength", catalog)
    assert resolved is not None
    assert [f.ref for f in resolved.data_spec.fields] == ["metric.headcount"]


def test_key_slug_is_stable():
    assert GlossaryTerm(term="Take-home Pay!", definition="x").key() == "take_home_pay"


def test_synonyms_for_ref_only_includes_terms_with_ref(catalog):
    catalog.glossary.append(GlossaryTerm(term="Probation", definition="Trial period.", ref=None))
    syn = catalog.synonyms_for_ref()
    assert "metric.total_net" in syn
    assert "in-hand salary" in syn["metric.total_net"]
    # The documentary term (no ref) contributes nothing to resolution.
    assert all("Probation" not in v for v in syn.values())
