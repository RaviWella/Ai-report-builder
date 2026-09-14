"""
Exclude rows with NULL in key business columns unless the user asked for null/missing data.

Typical failure: ORDER BY basic_salary DESC while NULL salaries appear in the result grid.
"""
from __future__ import annotations

import logging
import re
from enum import Enum
from typing import Optional

from .sql_aliases import alias_to_table_short

if False:  # TYPE_CHECKING without circular import noise
    from ..schema_broker import SchemaGrounding

logger = logging.getLogger("ai_services.datamart.sql_null_policy")

_WHERE_BOUNDARY = re.compile(
    r"\b(GROUP\s+BY|ORDER\s+BY|LIMIT|HAVING|UNION|OFFSET)\b",
    re.IGNORECASE,
)

_INCLUDE_NULL_INTENT = re.compile(
    r"\b(?:include|show|with|keep|return)\s+(?:the\s+)?(?:null|nulls|blank|empty|missing|unknown)\b"
    r"|\b(?:null|nulls|blank|missing)\s+(?:values?|rows?|records?)\b"
    r"|\bunspecified\b",
    re.IGNORECASE,
)

_WANTS_NULL_ROWS = re.compile(
    r"\b(?:is\s+null|are\s+null)\b"
    r"|\bwithout\s+(?:a\s+)?\w+"
    r"|\bno\s+(?:\w+\s+){0,3}(?:assigned|set|recorded|manager|supervisor|salary|title|branch)\b"
    r"|\bmissing\s+(?:\w+\s+){0,2}(?:manager|supervisor|salary|title|branch|data)\b"
    r"|\bblank\s+\w+",
    re.IGNORECASE,
)

_ORDER_BY_RE = re.compile(
    r"\bORDER\s+BY\s+(.+?)(?=\s+LIMIT\b|\s+OFFSET\b|;|\s*$)",
    re.IGNORECASE | re.DOTALL,
)

_ORDER_EXPR_CLEAN = re.compile(
    r"\s+(?:ASC|DESC)(?:\s+NULLS\s+(?:LAST|FIRST))?\s*$",
    re.IGNORECASE,
)

_QUALIFIED_COL = re.compile(
    r"^(?P<alias>\w+)\.(?P<col>\w+)(?:\s+(?:ASC|DESC))?(?:\s+NULLS\s+(?:LAST|FIRST))?$",
    re.IGNORECASE,
)

_BARE_COL = re.compile(
    r"^(?P<col>\w+)(?:\s+(?:ASC|DESC))?(?:\s+NULLS\s+(?:LAST|FIRST))?$",
    re.IGNORECASE,
)

_NAME_COLS = frozenset(
    {
        "emp_fullname",
        "full_name",
        "employee_name",
        "candidate_name",
        "emp_name",
    }
)

_LIST_ENTITIES = re.compile(
    r"\b(?:employee|staff|candidate|workers?|headcount|listing|list|show\s+me|report)\b",
    re.IGNORECASE,
)


class NullRowIntent(str, Enum):
    FILTER_DEFAULT = "filter_default"
    INCLUDE_OR_NULL_FOCUS = "include_or_null_focus"


def classify_null_row_intent(question: str) -> NullRowIntent:
    text = (question or "").strip()
    if not text:
        return NullRowIntent.FILTER_DEFAULT
    if _INCLUDE_NULL_INTENT.search(text) or _WANTS_NULL_ROWS.search(text):
        return NullRowIntent.INCLUDE_OR_NULL_FOCUS
    return NullRowIntent.FILTER_DEFAULT


def _insert_where_predicates(sql: str, preds: list[str]) -> str:
    if not preds:
        return sql
    clause = " AND ".join(preds)
    if re.search(r"\bWHERE\b", sql, flags=re.IGNORECASE):
        return re.sub(
            r"(\bWHERE\b)",
            rf"\1 {clause} AND",
            sql,
            count=1,
            flags=re.IGNORECASE,
        )
    m = _WHERE_BOUNDARY.search(sql)
    if m:
        pos = m.start()
        return f"{sql[:pos]} WHERE {clause} {sql[pos:]}"
    trimmed = sql.rstrip().rstrip(";")
    return f"{trimmed} WHERE {clause}"


def _already_has_is_not_null(sql: str, qualified: str) -> bool:
    """``qualified`` is ``alias.col`` or ``col``."""
    low = sql.lower()
    q = qualified.lower()
    if f"{q} is not null" in low:
        return True
    if "." not in q:
        return bool(re.search(rf"\b{re.escape(q)}\s+is\s+not\s+null\b", low))
    return False


def _order_by_predicates(sql: str) -> list[str]:
    m = _ORDER_BY_RE.search(sql)
    if not m:
        return []
    segment = m.group(1).strip()
    aliases = alias_to_table_short(sql)
    default_alias = next(iter(aliases.keys()), None) if len(aliases) == 1 else None
    preds: list[str] = []
    seen: set[str] = set()

    for raw_part in segment.split(","):
        part = raw_part.strip()
        if not part or part.upper().startswith("CASE"):
            continue
        part = _ORDER_EXPR_CLEAN.sub("", part).strip()
        qm = _QUALIFIED_COL.match(part)
        if qm:
            qual = f"{qm.group('alias')}.{qm.group('col')}"
        else:
            bm = _BARE_COL.match(part)
            if not bm or not default_alias:
                continue
            qual = f"{default_alias}.{bm.group('col')}"
        if qual.lower() in seen:
            continue
        if _already_has_is_not_null(sql, qual):
            continue
        seen.add(qual.lower())
        preds.append(f"{qual} IS NOT NULL")
    return preds


def _name_column_predicates(sql: str, question: str) -> list[str]:
    """Drop rows with NULL names when listing people (unless user asked about nulls)."""
    if not _LIST_ENTITIES.search(question or ""):
        return []
    aliases = alias_to_table_short(sql)
    preds: list[str] = []
    for alias, _table in aliases.items():
        for col in _NAME_COLS:
            qual = f"{alias}.{col}"
            if qual.lower() not in sql.lower():
                continue
            if _already_has_is_not_null(sql, qual):
                continue
            preds.append(f"{qual} IS NOT NULL")
    return preds


def apply_null_row_policy(
    sql: str,
    *,
    question: str,
) -> tuple[str, bool]:
    """
    Add ``IS NOT NULL`` on ORDER BY keys (and name columns for people listings).

    Returns ``(sql, changed)``.
    """
    text = (sql or "").strip()
    if not text or text.upper() == "NONE":
        return sql, False
    if not re.match(r"(?is)^(WITH|SELECT)\b", text):
        return sql, False

    if classify_null_row_intent(question) is NullRowIntent.INCLUDE_OR_NULL_FOCUS:
        logger.debug("null row policy skipped (user asked about null/missing values)")
        return sql, False

    preds = _order_by_predicates(text) + _name_column_predicates(text, question)
    if not preds:
        return sql, False

    # Dedupe while preserving order
    unique: list[str] = []
    seen: set[str] = set()
    for p in preds:
        key = p.lower()
        if key not in seen:
            seen.add(key)
            unique.append(p)

    out = _insert_where_predicates(text, unique)
    if out.strip() == text.strip():
        return sql, False

    logger.info("Applied null filters (%s) for question", ", ".join(unique))
    return out, True
