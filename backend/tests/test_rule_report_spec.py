"""Rule-report spec (Phase 1) — the Golden Key OT report parses + validates, and
malformed specs are rejected. Pure domain-model tests, no DB."""

import pytest

from app.domain.rule_report import RuleReportSpec

OT_SPEC = {
    "name": "golden_key_ot_monthly",
    "source": "mart.mart_attendance_daily",
    "grain": ["employee_no", "year_month"],
    "constants": {"min_per_day": 6, "month_days": 30, "ph": 8, "halfday": 4},
    "day_value": {
        "define": {"adj_worked": "coalesce(worked_hours, 0)"},
        "cases": [
            {"when": "is_public_holiday and not worked_on_holiday", "value": "ph"},
            {"when": "worked_on_holiday", "value": "adj_worked + ph"},
            {"when": "leave_category == 'Lieu Leave'", "value": "ph"},
            {"when": "leave_category == 'Full Day Leave' or day_portion == 'Full Day'", "value": "ph"},
            {"when": "day_portion in ('First Half', 'Second Half')", "value": "adj_worked + halfday"},
            {"when": "leave_category == 'Short Leave'", "value": "adj_worked + leave_minutes / 60"},
            {"when": "days_nopay > 0", "value": "0"},
        ],
        "else": "adj_worked",
    },
    "rollup": {
        "total_qualifying": "sum(day_value)",
        "npl_days": "sum(days_nopay)",
    },
    "compute": {
        "applicable_min": "(month_days - npl_days) * min_per_day",
        "ot_hours": "max(0, total_qualifying - applicable_min)",
    },
    "output": ["employee_no", "year_month", "total_qualifying", "npl_days",
               "applicable_min", "ot_hours"],
    "filters": [
        {"name": "date_from", "type": "date", "required": True, "column": "work_date", "op": "gte"},
        {"name": "date_to", "type": "date", "required": True, "column": "work_date", "op": "lte"},
        {"name": "employee_no", "type": "string", "column": "employee_no", "op": "eq"},
        {"name": "department", "type": "string", "column": "department", "op": "eq"},
    ],
}


def test_ot_spec_parses_and_validates():
    spec = RuleReportSpec.model_validate(OT_SPEC)
    assert spec.name == "golden_key_ot_monthly"
    assert spec.grain == ["employee_no", "year_month"]
    assert len(spec.day_value.cases) == 7
    assert spec.day_value.else_value == "adj_worked"   # `else` alias round-trips
    assert spec.constants["ph"] == 8
    assert spec.derived_names() == {"total_qualifying", "npl_days", "applicable_min", "ot_hours"}


def test_spec_round_trips_by_alias():
    # Stored as presentation_spec.spec (by_alias) and loaded back on run. The per-row
    # value serialises under its canonical `row_value` key; the `else` alias survives.
    spec = RuleReportSpec.model_validate(OT_SPEC)
    dumped = spec.model_dump(by_alias=True)
    assert "row_value" in dumped                 # canonical name on the way out
    assert "else" in dumped["row_value"]
    again = RuleReportSpec.model_validate(dumped)
    assert again.day_value.else_value == "adj_worked"
    assert len(again.day_value.cases) == 7


def test_day_value_and_row_value_are_interchangeable():
    # Legacy specs use `day_value`; new specs use `row_value`. Both load the same.
    base = {k: v for k, v in OT_SPEC.items() if k != "day_value"}
    a = RuleReportSpec.model_validate({**base, "day_value": OT_SPEC["day_value"]})
    b = RuleReportSpec.model_validate({**base, "row_value": OT_SPEC["day_value"]})
    assert a.day_value.else_value == b.day_value.else_value == "adj_worked"


def test_day_value_requires_cases():
    bad = {**OT_SPEC, "day_value": {"cases": [], "else": "0"}}
    with pytest.raises(ValueError):
        RuleReportSpec.model_validate(bad)


def test_name_must_be_snake():
    with pytest.raises(ValueError):
        RuleReportSpec.model_validate({**OT_SPEC, "name": "Golden Key"})


def test_source_must_be_schema_table():
    with pytest.raises(ValueError):
        RuleReportSpec.model_validate({**OT_SPEC, "source": "mart_attendance_daily"})


def test_grain_required():
    with pytest.raises(ValueError):
        RuleReportSpec.model_validate({**OT_SPEC, "grain": []})


def test_rollup_compute_name_clash_rejected():
    bad = {**OT_SPEC,
           "rollup": {"ot_hours": "sum(day_value)"},   # clashes with compute.ot_hours
           "compute": {"ot_hours": "max(0, ot_hours)"}}
    with pytest.raises(ValueError):
        RuleReportSpec.model_validate(bad)


# ---- having / order_by / filter.expose_as (all optional — Golden Key doesn't use them) ----

def test_having_and_order_by_are_optional_and_default_empty():
    spec = RuleReportSpec.model_validate(OT_SPEC)
    assert spec.having is None
    assert spec.order_by == []


def test_having_and_order_by_round_trip():
    spec = RuleReportSpec.model_validate({
        **OT_SPEC, "having": "total_qualifying >= 1", "order_by": ["employee_no", "year_month"],
    })
    assert spec.having == "total_qualifying >= 1"
    assert spec.order_by == ["employee_no", "year_month"]


def test_filter_expose_as_round_trips():
    spec = RuleReportSpec.model_validate({
        **OT_SPEC,
        "filters": [*OT_SPEC["filters"], {"name": "date_to", "type": "date", "column": "work_date",
                                          "op": "lte", "expose_as": "end_date"}],
    })
    exposed = [f for f in spec.filters if f.expose_as]
    assert exposed[0].expose_as == "end_date"


def test_expose_as_must_be_snake_case():
    bad = {**OT_SPEC, "filters": [{"name": "date_to", "expose_as": "End Date"}]}
    with pytest.raises(ValueError):
        RuleReportSpec.model_validate(bad)


def test_expose_as_clashing_with_rollup_rejected():
    bad = {**OT_SPEC, "filters": [{"name": "date_to", "expose_as": "total_qualifying"}]}
    with pytest.raises(ValueError):
        RuleReportSpec.model_validate(bad)


def test_order_by_referencing_expose_as_rejected():
    bad = {**OT_SPEC,
           "filters": [{"name": "date_to", "expose_as": "end_date"}],
           "order_by": ["end_date"]}
    with pytest.raises(ValueError):
        RuleReportSpec.model_validate(bad)
