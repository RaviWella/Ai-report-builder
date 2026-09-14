"""G2 — certified-metrics governance tests (no DB required).

Covers the metric-definition model fields, the AI projection surfacing `certified`,
and the (pure) re-certification guard that blocks silent overwrite of a certified
metric.
"""

from __future__ import annotations

import pytest

from app.domain.enums import AggFn
from app.domain.semantic import MetricDef
from app.query_engine import guards
from app.services.metrics_service import assert_recertification_ok
from app.services.semantic_seed import build_seed_catalog


def _metric(key: str, *, certified: bool = False) -> MetricDef:
    return MetricDef(
        key=key, label=key.title(), kind="aggregate", agg=AggFn.SUM,
        ref="payroll.gross", certified=certified,
    )


def test_metricdef_certification_fields_default_off():
    m = _metric("total_gross")
    assert m.certified is False
    assert m.certified_by is None and m.certified_at is None and m.owner is None


def test_metadata_for_ai_surfaces_certified():
    cat = build_seed_catalog("t", 1)
    cat.metrics = [_metric("total_gross", certified=True), _metric("draft_metric")]
    metrics = [m for m in cat.metadata_for_ai() if m.get("is_metric")]
    by_ref = {m["ref"]: m for m in metrics}
    assert by_ref["metric.total_gross"]["certified"] is True
    assert by_ref["metric.draft_metric"]["certified"] is False


def test_recert_guard_allows_first_definition():
    assert_recertification_ok(None, _metric("x"))  # no prior → fine


def test_recert_guard_allows_editing_uncertified():
    assert_recertification_ok(_metric("x", certified=False), _metric("x", certified=False))


def test_recert_guard_blocks_uncertified_overwrite_of_certified():
    prior = _metric("headcount", certified=True)
    with pytest.raises(guards.GuardError):
        assert_recertification_ok(prior, _metric("headcount", certified=False))


def test_recert_guard_allows_explicit_recertification():
    prior = _metric("headcount", certified=True)
    assert_recertification_ok(prior, _metric("headcount", certified=True))  # deliberate re-cert
