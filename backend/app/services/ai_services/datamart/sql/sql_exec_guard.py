"""Guards for warehouse SELECT execution (timeouts, row caps)."""
from __future__ import annotations

import re

from typing import TYPE_CHECKING, Optional

from ..config import MAX_RESULT_ROWS

if TYPE_CHECKING:
    from ..schema_broker import SchemaGrounding

_LIMIT_TAIL_RE = re.compile(r"\bLIMIT\s+(\d+)\s*(;)?\s*\Z", re.IGNORECASE)

_TIMEOUT_MARKERS = (
    "statement timeout",
    "querycanceled",
    "canceling statement",
    "cancelled statement",
    "lock timeout",
    "execution time exceeded",
    "timeout expired",
)


def is_warehouse_timeout_error(message: str) -> bool:
    low = (message or "").lower()
    return any(m in low for m in _TIMEOUT_MARKERS)


def validate_sql_against_grounding(
    sql: str,
    grounding: Optional["SchemaGrounding"],
) -> Optional[str]:
    """Last-line binding check before warehouse execute (same rules as validate_sql)."""
    if grounding is None or not grounding.columns_by_table:
        return None
    from .sql_binding import validate_sql_bindings

    return validate_sql_bindings(sql, grounding)


def ensure_select_limit(sql: str, max_rows: int | None = None) -> str:
    """
    Ensure the outer query has ``LIMIT n`` with ``n <= max_rows``.
    Appends LIMIT when missing (common cause of long warehouse runs).
    """
    cap = max(1, int(max_rows if max_rows is not None else MAX_RESULT_ROWS))
    text = sql.strip()
    if not text:
        return sql
    m = _LIMIT_TAIL_RE.search(text)
    if not m:
        return f"{text.rstrip(';')}\nLIMIT {cap}"
    n = int(m.group(1))
    if n <= cap:
        return text
    semi = m.group(2) or ""
    new_tail = f"LIMIT {cap}{semi}"
    return text[: m.start()] + new_tail + text[m.end() :]
