"""TIME block — symbolic period token resolution (the compiler's current_period())."""

from datetime import date

import pytest

from app.query_engine.periods import is_period_token, resolve_period_value

T = date(2026, 6, 30)


def test_calendar_tokens():
    assert resolve_period_value("@period:current_year", T) == 2026
    assert resolve_period_value("@period:last_year", T) == 2025
    assert resolve_period_value("@period:current_month", T) == 6


def test_rolling_window_tokens_return_date_objects():
    # date objects (not strings) so SQLAlchemy binds them against a DATE column.
    assert resolve_period_value("@period:months_ago:12", T) == date(2025, 6, 30)
    assert resolve_period_value("@period:days_ago:30", T) == date(2026, 5, 31)


def test_month_clamp_on_short_month():
    # 31 Mar minus 1 month must not produce an invalid 31 Feb.
    assert resolve_period_value("@period:months_ago:1", date(2026, 3, 31)) == date(2026, 2, 28)


@pytest.mark.parametrize("v", ["active", 2026, None, "employee.status"])
def test_non_tokens_pass_through(v):
    assert resolve_period_value(v, T) == v
    assert not is_period_token(v)


def test_unknown_token_is_left_untouched():
    assert resolve_period_value("@period:nonsense", T) == "@period:nonsense"
