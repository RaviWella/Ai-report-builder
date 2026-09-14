"""Hybrid deterministic resolver tests (no DB) — Excel-style field matching +
rule-based filters/grouping + the matched/unmatched mapping report."""

from __future__ import annotations

import pytest

from app.domain.enums import FilterOp
from app.services.nl_hybrid import hybrid_resolve
from app.services.semantic_seed import build_seed_catalog


@pytest.fixture
def catalog():
    return build_seed_catalog("t", 1)


def _refs(res):
    return {f.ref for f in res.matched}


def test_field_list_matches_deterministically(catalog):
    res = hybrid_resolve("Show employee name, department, basic salary", catalog)
    assert res is not None
    # Concept-lock: in an all-employee field list, "basic salary" resolves to the
    # EMPLOYEE field (no needless payroll join), not payroll.basic.
    assert {"employee.full_name", "employee.department", "employee.current_basic"} <= _refs(res)
    assert res.unmatched == []
    assert res.data_spec.entity == "employee"


def test_concept_lock_is_context_sensitive_and_deterministic(catalog):
    # Same words, different context → the dominant entity wins, every time.
    emp = hybrid_resolve("employee name, department, basic salary", catalog)
    assert "employee.current_basic" in _refs(emp) and "payroll.basic" not in _refs(emp)

    pay = hybrid_resolve("basic salary, gross salary, total deductions", catalog)
    pay_refs = _refs(pay)
    # gross/deductions exist only on payroll, so "basic salary" locks to payroll too.
    assert "payroll.basic" in pay_refs or any(r.startswith("metric.") for r in pay_refs)
    assert "employee.current_basic" not in pay_refs

    # Reproducible: identical prompt always yields identical refs.
    assert _refs(hybrid_resolve("employee name, department, basic salary", catalog)) == _refs(emp)


def test_legit_cross_entity_report_is_preserved(catalog):
    # A field only available on another entity is still included (with the join).
    res = hybrid_resolve("employee name, net salary", catalog)
    refs = _refs(res)
    assert "employee.full_name" in refs
    assert any("net" in r.lower() for r in refs)


def test_unmatched_fields_are_reported_not_swallowed(catalog):
    # compa-ratio / business unit aren't in the seed catalogue (branch now is)
    res = hybrid_resolve("employee name, compa-ratio, business unit", catalog)
    assert "employee.full_name" in _refs(res)
    low = " ".join(res.unmatched).lower()
    assert "compa" in low and "business" in low


def test_time_block_this_month_emits_symbolic_period(catalog):
    res = hybrid_resolve("total net pay by department this month", catalog)
    assert res is not None
    vals = {(f.ref, f.value) for f in res.data_spec.filters}
    assert ("payroll.year", "@period:current_year") in vals
    assert ("payroll.month", "@period:current_month") in vals


def test_time_block_rolling_window_on_date_field(catalog):
    res = hybrid_resolve("employees who joined in the last 12 months", catalog)
    assert res is not None
    join = [f for f in res.data_spec.filters if f.ref == "employee.join_date"]
    assert join and join[0].op == FilterOp.GTE and join[0].value == "@period:months_ago:12"
    # filter-only prompt still yields some identifying columns
    assert "employee.full_name" in _refs(res)


def test_filter_only_does_not_mask_unmatched_field(catalog):
    # compa-ratio isn't in the catalogue; we must NOT silently return a name list.
    assert hybrid_resolve("show me compa-ratio for active staff", catalog) is None


def test_status_filter_is_parsed(catalog):
    res = hybrid_resolve("active employees — include full name, department", catalog)
    assert res is not None
    status = [f for f in res.data_spec.filters if f.ref == "employee.status"]
    assert status and status[0].op == FilterOp.EQ and status[0].value == "active"
    assert any("Employment Status" in d for d in res.filters)


def test_tenure_comparison_filter_is_parsed(catalog):
    res = hybrid_resolve("include full name where tenure is more than 3 years", catalog)
    assert res is not None
    ten = [f for f in res.data_spec.filters if f.ref == "employee.tenure_years"]
    assert ten and ten[0].op == FilterOp.GT and ten[0].value == 3.0


def test_at_least_maps_to_gte(catalog):
    res = hybrid_resolve("full name, at least 5 years tenure", catalog)
    ten = [f for f in res.data_spec.filters if f.ref == "employee.tenure_years"]
    assert ten and ten[0].op == FilterOp.GTE and ten[0].value == 5.0


def test_rollup_grouping(catalog):
    res = hybrid_resolve("headcount by department", catalog)
    assert res is not None
    assert res.data_spec.group_by == ["employee.department"]
    assert res.data_spec.aggregations  # a count/agg was produced
    assert "grouped by Department" in res.rationale


def test_gibberish_returns_none_so_caller_can_fall_back(catalog):
    assert hybrid_resolve("asdf qwer zxcv blorp", catalog) is None


def test_confidence_drops_with_many_unmatched(catalog):
    good = hybrid_resolve("employee name, department, designation", catalog)
    poor = hybrid_resolve("employee name, branch, business unit, compa-ratio, foobar", catalog)
    assert good.confidence > poor.confidence
