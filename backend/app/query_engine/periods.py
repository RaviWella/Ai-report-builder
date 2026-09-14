"""Relative-period resolution — the compiler's `current_period()`.

A spec carries a TIME block symbolically (e.g. a filter value `@period:current_year`)
rather than a baked literal date. The compiler resolves the token to a concrete
value at run time, here. Two wins:

  - the spec stays reusable and cacheable — "this month" resolves to the current
    month every time it runs, so a learned/saved report never goes stale;
  - no language model and no string-built SQL are involved — the value is computed
    deterministically and still bound as a parameter by the filter builder.

Tokens (all `@period:` prefixed):
  current_year · last_year      -> int year
  current_month                 -> int month (1-12)
  months_ago:<n> · days_ago:<n> -> ISO date (today shifted back), for date columns
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta

PERIOD_PREFIX = "@period:"


def _months_ago(today: date, n: int) -> date:
    """`today` shifted back `n` whole months, clamped to a valid day-of-month."""
    total = today.year * 12 + (today.month - 1) - n
    year, month = divmod(total, 12)
    month += 1
    day = min(today.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def is_period_token(value: object) -> bool:
    return isinstance(value, str) and value.startswith(PERIOD_PREFIX)


def resolve_period_value(value: object, today: date | None = None) -> object:
    """Resolve a `@period:` token to a concrete value; pass anything else through."""
    if not is_period_token(value):
        return value
    today = today or date.today()
    tok = value[len(PERIOD_PREFIX):]  # type: ignore[index]
    if tok == "current_year":
        return today.year
    if tok == "last_year":
        return today.year - 1
    if tok == "current_month":
        return today.month
    # Return real date objects so SQLAlchemy binds them against a DATE column (a
    # string would trigger 'operator does not exist: date >= varchar').
    if tok.startswith("months_ago:"):
        return _months_ago(today, int(tok.split(":")[1]))
    if tok.startswith("days_ago:"):
        return today - timedelta(days=int(tok.split(":")[1]))
    return value  # unknown token — leave as-is (validation/guards will surface it)
