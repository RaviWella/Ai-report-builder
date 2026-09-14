"""Read-only SQL checks for client-side execute overrides."""
from __future__ import annotations

import re
from typing import Optional

from ..llm.llm_response import validate_sql_syntax

_FORBIDDEN_DML = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|GRANT|REVOKE)\b",
    re.IGNORECASE,
)


def validate_readonly_sql(sql: str) -> Optional[str]:
    """
    Return an error message if ``sql`` is not an allowed read-only query, else None.
    """
    text = (sql or "").strip()
    if not text:
        return "SQL is empty."
    if not re.match(r"(?is)^(WITH|SELECT)\b", text):
        return "Only SELECT queries (WITH/CTE allowed) may be executed."
    if _FORBIDDEN_DML.search(text):
        return "Only read-only SELECT queries are allowed."
    return validate_sql_syntax(text)
