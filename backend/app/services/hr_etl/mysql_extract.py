"""MySQL-specific ETL extract helpers (chunked reads, transient error detection)."""
from __future__ import annotations

from sqlalchemy.exc import DBAPIError, OperationalError

# MySQL server/client codes for dropped connections during long reads.
TRANSIENT_MYSQL_ERROR_CODES: frozenset[int] = frozenset({2006, 2013})


def is_transient_mysql_error(exc: BaseException) -> bool:
    """True when the error looks like a dropped MySQL connection mid-query."""
    if not isinstance(exc, (OperationalError, DBAPIError)):
        return False
    orig = getattr(exc, "orig", None)
    if orig is not None and getattr(orig, "args", None):
        try:
            return int(orig.args[0]) in TRANSIENT_MYSQL_ERROR_CODES
        except (TypeError, ValueError):
            pass
    text = str(exc).lower()
    return "lost connection" in text or "server has gone away" in text


def wrap_keyset_chunk_sql(inner_sql: str, pk_column: str) -> str:
    """Wrap extractor SQL for PK-based keyset pagination (short-lived connections)."""
    inner = inner_sql.rstrip().rstrip(";")
    return (
        f"SELECT * FROM (\n{inner}\n) _etl_chunk\n"
        f"WHERE {pk_column} > :_chunk_after\n"
        f"ORDER BY {pk_column}\n"
        f"LIMIT :_chunk_limit"
    )
