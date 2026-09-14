"""Regression test for a real production bug: a runtime date/date-range filter
against a native `date` column crashed with
`psycopg.errors.UndefinedFunction: operator does not exist: date >= character
varying`. Runtime filter values always arrive as plain JSON strings (a browser
<input type=date> sends "2026-09-01"), and the dynamically-introspected
column (sql_builder.TableRegistry) carries no SQLAlchemy type, so a raw
string bind fell back to a generic/varchar type — which Postgres has no
comparison operator for against `date`. Fixed by parsing the value into a
real `datetime.date`/`datetime.datetime` object when the field's own semantic
type is known (compiler._field_type_of -> filters.build_filter's field_type
param) — SQLAlchemy then infers the correct bind type from the Python value
itself. No DB needed — asserts the actual bound parameter's Python type.
"""

from __future__ import annotations

import datetime

from sqlalchemy.dialects import postgresql

from app.domain.report_spec import DataSpec
from app.query_engine.compiler import compile_query
from app.services.semantic_seed import build_seed_catalog


def _bound_params(spec: DataSpec, catalog, params: dict) -> dict:
    compiled = compile_query(spec, catalog, params)
    return compiled.statement.compile(dialect=postgresql.dialect()).params


def test_between_on_a_date_field_binds_real_date_objects():
    catalog = build_seed_catalog("tenant_test", 1)
    spec = DataSpec.model_validate({
        "entity": "employee",
        "fields": [{"ref": "employee.full_name"}],
        "filters": [{"ref": "employee.join_date", "op": "between", "param": "range"}],
    })
    bound = _bound_params(spec, catalog, {"range": ["2026-09-01", "2026-09-02"]})
    dates = [v for v in bound.values() if isinstance(v, datetime.date)]
    assert sorted(dates) == [datetime.date(2026, 9, 1), datetime.date(2026, 9, 2)]


def test_gte_on_a_date_field_binds_a_real_date_object():
    catalog = build_seed_catalog("tenant_test", 1)
    spec = DataSpec.model_validate({
        "entity": "employee",
        "fields": [{"ref": "employee.full_name"}],
        "filters": [{"ref": "employee.join_date", "op": "gte", "param": "from"}],
    })
    bound = _bound_params(spec, catalog, {"from": "2026-09-01"})
    assert datetime.date(2026, 9, 1) in bound.values()


def test_eq_on_a_non_date_field_stays_a_plain_string():
    # Guard against over-applying the parse — a plain string/dimension field's
    # value must stay exactly as given, never coerced into a date.
    catalog = build_seed_catalog("tenant_test", 1)
    spec = DataSpec.model_validate({
        "entity": "employee",
        "fields": [{"ref": "employee.full_name"}],
        "filters": [{"ref": "employee.full_name", "op": "eq", "value": "Jane Doe"}],
    })
    bound = _bound_params(spec, catalog, {})
    assert "Jane Doe" in bound.values()
