"""L1 — required-period-filter guard tests (no DB required).

OFF by default → no behaviour change. ON → period-grained reports must carry a
period filter; non-period reports are never affected.
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
def require_period(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "query_require_period_filter", True, raising=False)


def _payroll_no_filter():
    return DataSpec.model_validate(
        {"entity": "employee",
         "fields": [{"ref": "employee.full_name"}, {"ref": "payroll.basic"}]}
    )


def test_off_by_default_period_report_compiles(catalog):
    # default config: guard disabled → a payroll report with no period filter is fine
    compile_query(_payroll_no_filter(), catalog, {})


def test_on_rejects_period_report_without_filter(catalog, require_period):
    with pytest.raises(guards.GuardError):
        compile_query(_payroll_no_filter(), catalog, {})


def test_on_allows_period_report_with_static_filter(catalog, require_period):
    spec = DataSpec.model_validate(
        {"entity": "employee",
         "fields": [{"ref": "employee.full_name"}, {"ref": "payroll.basic"}],
         "filters": [{"ref": "payroll.year", "op": "eq", "value": 2024}]}
    )
    compile_query(spec, catalog, {})  # no raise


def test_on_allows_period_report_with_runtime_param(catalog, require_period):
    spec = DataSpec.model_validate(
        {"entity": "employee",
         "fields": [{"ref": "employee.full_name"}, {"ref": "payroll.basic"}],
         "filters": [{"ref": "payroll.month", "op": "eq", "param": "month"}]}
    )
    compile_query(spec, catalog, {"month": 6})  # no raise


def test_on_does_not_affect_non_period_report(catalog, require_period):
    # employee-only report has no period-grained entity → unaffected by the guard
    spec = DataSpec.model_validate(
        {"entity": "employee", "fields": [{"ref": "employee.full_name"}]}
    )
    compile_query(spec, catalog, {})  # no raise
