"""Canonical metrics — metric.<key> resolves to correct, governed SQL."""

from __future__ import annotations

import pytest
from sqlalchemy.dialects import postgresql

from app.domain.enums import AggFn, FilterOp
from app.domain.report_spec import DataSpec
from app.domain.semantic import MetricDef, MetricFilter
from app.query_engine import guards
from app.query_engine.compiler import compile_query
from app.services.semantic_seed import build_seed_catalog


@pytest.fixture
def catalog():
    cat = build_seed_catalog("t", 1)
    cat.metrics = [
        MetricDef(key="total_gross", label="Total Gross", kind="aggregate", agg=AggFn.SUM, ref="payroll.gross"),
        MetricDef(key="total_ded", label="Total Deductions", kind="aggregate", agg=AggFn.SUM, ref="payroll.deductions"),
        MetricDef(key="net_total", label="Net Total", kind="formula", expression="metric.total_gross - metric.total_ded"),
        MetricDef(key="headcount", label="Headcount", kind="count", ref="employee.emp_no", distinct=True),
        MetricDef(key="active_headcount", label="Active Headcount", kind="count", ref="employee.emp_no",
                  distinct=True, filters=[MetricFilter(ref="employee.status", op=FilterOp.EQ, value="active")]),
    ]
    return cat


def _sql(spec, catalog):
    return str(compile_query(spec, catalog, {}).statement.compile(dialect=postgresql.dialect()))


def test_aggregate_metric_compiles_to_agg(catalog):
    sql = _sql(DataSpec.model_validate({"entity": "employee", "fields": [{"ref": "metric.total_gross"}]}), catalog)
    assert "sum(" in sql.lower()


def test_formula_metric_is_arithmetic_of_aggregates(catalog):
    sql = _sql(DataSpec.model_validate({"entity": "employee", "fields": [{"ref": "metric.net_total"}]}), catalog).lower()
    assert "sum(" in sql and " - " in sql  # sum(gross) - sum(deductions)


def test_count_distinct_metric(catalog):
    sql = _sql(DataSpec.model_validate({"entity": "employee", "fields": [{"ref": "metric.headcount"}]}), catalog).lower()
    assert "count(distinct" in sql


def test_filtered_metric_uses_aggregate_filter(catalog):
    sql = _sql(DataSpec.model_validate({"entity": "employee", "fields": [{"ref": "metric.active_headcount"}]}), catalog).lower()
    assert "filter (where" in sql  # count(...) FILTER (WHERE status = ...)


def test_dimension_plus_metric_auto_groups(catalog):
    spec = DataSpec.model_validate(
        {"entity": "employee", "fields": [{"ref": "employee.department"}, {"ref": "metric.total_gross"}]}
    )
    sql = _sql(spec, catalog).lower()
    assert "group by" in sql and "sum(" in sql


def test_unknown_metric_rejected(catalog):
    with pytest.raises(guards.GuardError):
        compile_query(DataSpec.model_validate({"entity": "employee", "fields": [{"ref": "metric.nope"}]}), catalog, {})


def test_metric_join_is_validated(catalog):
    # net_total references payroll measures → payroll must be join-reachable from employee.
    guards.validate_refs(
        DataSpec.model_validate({"entity": "employee", "fields": [{"ref": "metric.net_total"}]}), catalog
    )
    guards.validate_joins(
        DataSpec.model_validate({"entity": "employee", "fields": [{"ref": "metric.net_total"}]}), catalog
    )
