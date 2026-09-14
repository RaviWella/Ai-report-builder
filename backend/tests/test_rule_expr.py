"""Safe rule-expression compiler (Phase 2) — the OT expressions compile to the
right SQL, and anything outside the whitelist is rejected. No DB, no eval."""

import pytest
from sqlalchemy import column
from sqlalchemy.dialects import postgresql

from app.query_engine import guards
from app.query_engine.rule_expr import compile_expr

# namespace: source columns (symbolic) + constants (scalars)
NS = {
    "worked_hours": column("worked_hours"),
    "late_minutes": column("late_minutes"),
    "leave_category": column("leave_category"),
    "day_portion": column("day_portion"),
    "is_public_holiday": column("is_public_holiday"),
    "worked_on_holiday": column("worked_on_holiday"),
    "days_nopay": column("days_nopay"),
    "leave_minutes": column("leave_minutes"),
    # constants / prior derived
    "ph": 8, "halfday": 4, "min_per_day": 6, "month_days": 30,
    "adj_worked": column("worked_hours"),
    "total_qualifying": column("total_qualifying"),
    "npl_days": column("npl_days"),
    "applicable_min": column("applicable_min"),
}


def _sql(expr: str) -> str:
    el = compile_expr(expr, NS)
    return str(el.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))


def test_arithmetic_and_constants():
    assert "worked_hours + 4" in _sql("adj_worked + halfday")


def test_boolean_and_not():
    s = _sql("is_public_holiday AND NOT worked_on_holiday".lower())
    assert "AND" in s and "NOT" in s


def test_in_membership():
    s = _sql("day_portion in ('First Half', 'Second Half')")
    assert "IN (" in s and "First Half" in s


def test_equality_string():
    assert "leave_category = 'Lieu Leave'" in _sql("leave_category == 'Lieu Leave'")


def test_greatest_from_max():
    assert "greatest(" in _sql("max(0, total_qualifying - applicable_min)")


def test_coalesce_and_div():
    s = _sql("coalesce(leave_minutes, 0) / 60")
    assert "coalesce(leave_minutes, 0) /" in s and "60" in s


def test_full_compute_formula():
    assert "(30 - npl_days) * 6" in _sql("(month_days - npl_days) * min_per_day")


@pytest.mark.parametrize("bad", [
    "__import__('os')",          # call to non-whitelisted name
    "worked_hours.foo",          # attribute access
    "foo(1)",                    # unknown function
    "unknown_col + 1",           # unknown name
    "worked_hours ** 2",         # disallowed operator (pow)
    "lambda: 1",                 # lambda
    "1 < 2 < 3",                 # chained comparison
])
def test_illegal_expressions_rejected(bad):
    with pytest.raises(guards.GuardError):
        compile_expr(bad, NS)


# ---- time(...) — a `time`-typed column can't be compared to a bare string literal
# in Postgres ("operator does not exist: time <= character varying"); time(...)
# casts the literal so the comparison type-checks. -----------------------------

TIME_NS = {**NS, "punch_in_time": column("punch_in_time"), "punch_out_time": column("punch_out_time")}


def _time_sql(expr: str) -> str:
    el = compile_expr(expr, TIME_NS)
    return str(el.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))


def test_time_literal_casts_for_comparison():
    s = _time_sql("punch_in_time <= time('14:30:00')")
    assert "CAST('14:30:00' AS TIME" in s
    assert "punch_in_time <= CAST" in s


def test_time_literal_usable_both_sides_of_a_window():
    s = _time_sql("punch_in_time >= time('12:00:00') and punch_out_time <= time('08:00:00')")
    assert s.count("CAST(") == 2


@pytest.mark.parametrize("bad", [
    "time(punch_in_time)",        # argument must be a literal, not a column
    "time('14:30:00', 'x')",      # exactly one argument
    "time(1430)",                 # argument must be a string
])
def test_time_rejects_non_literal_or_wrong_arity(bad):
    with pytest.raises(guards.GuardError):
        compile_expr(bad, TIME_NS)


# ---- hours_between(start, end) — decimal-hour duration between two time-like
# values (time/time for a same-day span, timestamp/timestamp for one that may
# cross midnight), via Postgres's native `-` plus extract(epoch from ...)/3600.

HB_NS = {**TIME_NS, "shift_start_time": column("shift_start_time"),
         "punch_out_datetime": column("punch_out_datetime"), "work_date": column("work_date")}


def _hb_sql(expr: str) -> str:
    el = compile_expr(expr, HB_NS)
    return str(el.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))


def test_hours_between_time_pair():
    s = _hb_sql("hours_between(punch_in_time, shift_start_time)")
    assert "EXTRACT(epoch FROM shift_start_time - punch_in_time)" in s
    assert "3600.0" in s   # divided by seconds-per-hour


def test_hours_between_composes_date_plus_time_for_the_second_operand():
    # building a "shift end, possibly next day" timestamp from a date + time via
    # `+` (Postgres resolves date + time -> timestamp natively), then diffing
    # against an already-correct timestamp column (e.g. punch_out_datetime).
    s = _hb_sql("hours_between(work_date + shift_start_time, punch_out_datetime)")
    assert "punch_out_datetime - (work_date + shift_start_time)" in s


@pytest.mark.parametrize("bad", [
    "hours_between(punch_in_time)",                    # exactly two arguments
    "hours_between(punch_in_time, shift_start_time, 1)",
])
def test_hours_between_rejects_wrong_arity(bad):
    with pytest.raises(guards.GuardError):
        compile_expr(bad, HB_NS)
