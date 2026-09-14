"""Same class of bug as test_date_filter_cast.py, for boolean/integer/decimal
fields: a filter value that arrives as a plain string (every runtime filter
value is raw JSON; every BUILDER-FIXED/static value is always typed as a
string in FilterPanel.tsx's own text field, regardless of the field's real
type) crashes with e.g. `operator does not exist: boolean = character
varying` against a native boolean/integer/numeric column, for the same
reason: the dynamically-introspected column carries no SQLAlchemy type.
filters.py's `_typed()` now parses these too. No DB needed — asserts the
actual bound parameter's Python type.
"""

from __future__ import annotations

from sqlalchemy.dialects import postgresql

from app.domain.report_spec import DataSpec
from app.query_engine.compiler import compile_query
from app.services.semantic_seed import build_seed_catalog


def _bound_params(spec: DataSpec, catalog, params: dict) -> dict:
    compiled = compile_query(spec, catalog, params)
    return compiled.statement.compile(dialect=postgresql.dialect()).params


def _rendered_sql(spec: DataSpec, catalog, params: dict) -> str:
    compiled = compile_query(spec, catalog, params)
    return str(compiled.statement.compile(dialect=postgresql.dialect()))


def test_static_boolean_string_value_becomes_a_real_bool():
    # FilterPanel.tsx's static-value TextField always stores a plain string —
    # "true" here — regardless of the field's declared type. SQLAlchemy
    # renders a real Python bool as the literal `true`/`false` (not a bind
    # param) — the bug was comparing the column to the STRING 'true', which
    # renders as a quoted `'true'` and crashes as
    # "operator does not exist: boolean = character varying".
    catalog = build_seed_catalog("tenant_test", 1)
    spec = DataSpec.model_validate({
        "entity": "employee",
        "fields": [{"ref": "employee.full_name"}],
        "filters": [{"ref": "employee.is_active", "op": "eq", "value": "true"}],
    })
    sql = _rendered_sql(spec, catalog, {})
    assert "is_active = true" in sql
    assert "'true'" not in sql


def test_runtime_boolean_no_string_becomes_false():
    catalog = build_seed_catalog("tenant_test", 1)
    spec = DataSpec.model_validate({
        "entity": "employee",
        "fields": [{"ref": "employee.full_name"}],
        "filters": [{"ref": "employee.is_active", "op": "eq", "param": "active"}],
    })
    sql = _rendered_sql(spec, catalog, {"active": "false"})
    assert "is_active = false" in sql
    assert "'false'" not in sql


def test_static_integer_string_value_becomes_a_real_int():
    catalog = build_seed_catalog("tenant_test", 1)
    spec = DataSpec.model_validate({
        "entity": "employee",
        "fields": [{"ref": "employee.full_name"}],
        "filters": [{"ref": "employee.age", "op": "gte", "value": "30"}],
    })
    bound = _bound_params(spec, catalog, {})
    assert 30 in bound.values()
    assert "30" not in bound.values()


def test_static_decimal_string_value_becomes_a_real_float():
    catalog = build_seed_catalog("tenant_test", 1)
    spec = DataSpec.model_validate({
        "entity": "employee",
        "fields": [{"ref": "employee.full_name"}],
        "filters": [{"ref": "employee.current_basic", "op": "lte", "value": "50000.5"}],
    })
    bound = _bound_params(spec, catalog, {})
    assert 50000.5 in bound.values()


def test_runtime_number_filter_already_a_number_is_left_alone():
    # The Viewer's own number control already sends a real JS number — this
    # must stay a no-op, never re-parsed or broken.
    catalog = build_seed_catalog("tenant_test", 1)
    spec = DataSpec.model_validate({
        "entity": "employee",
        "fields": [{"ref": "employee.full_name"}],
        "filters": [{"ref": "employee.age", "op": "gte", "param": "min_age"}],
    })
    bound = _bound_params(spec, catalog, {"min_age": 25})
    assert 25 in bound.values()
