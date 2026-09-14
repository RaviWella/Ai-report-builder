"""
SCD / versioning policy for warehouse tables with ``is_current``.

Most hr mart dimensions and facts store multiple row versions per business key;
``is_current = TRUE`` is the latest version. Queries that omit this filter often
return duplicate-looking rows (many historical versions + one current).

Historical questions should keep or explicitly filter older versions; default
analytics should restrict to current rows only.
"""
from __future__ import annotations

import logging
import re
from enum import Enum
from typing import TYPE_CHECKING, Optional

from ..sql.sql_aliases import alias_to_table_short

if TYPE_CHECKING:
    from ..schema_broker import SchemaGrounding

logger = logging.getLogger("ai_services.datamart.is_current")

_IS_CURRENT_COL = "is_current"

# User wants prior versions, snapshots, or explicit non-current rows.
_HISTORY_INTENT = re.compile(
    "|".join(
        (
            r"\bhistorical\b",
            r"\bhistory\b",
            r"\bemployment\s+history\b",
            r"\bsalary\s+history\b",
            r"\bdesignation\s+history\b",
            r"\bchange\s+history\b",
            r"\bversion\s+history\b",
            r"\ball\s+versions?\b",
            r"\bprevious\s+versions?\b",
            r"\bpast\s+versions?\b",
            r"\bover\s+time\b",
            r"\btrack\s+changes?\b",
            r"\bchanged\s+over\b",
            r"\bvalid_from\b",
            r"\bvalid_to\b",
            r"\bdbt_valid",
            r"\bpoint[- ]in[- ]time\b",
            r"\bas[- ]of\b",
            r"\bhr_snap\.",
            r"\bsnap_[a-z_]+\b",
            r"\bis_current\s*=\s*false\b",
            r"\bis_current\s+is\s+not\s+true\b",
            r"\bnon[- ]?current\b",
            r"\bsuperseded\b",
            r"\bscd\b",
            r"\binclude\b.+\b(?:versions?|history|inactive)\b",
            r"\bolder\s+versions?\b",
            r"\bprior\s+versions?\b",
            r"\bwas\s+(?:the\s+)?(?:manager|supervisor|designation|title|salary)\b",
        )
    ),
    re.IGNORECASE,
)

_ALIAS_IS_CURRENT_PRED = re.compile(
    r"\b(\w+)\.is_current\s*(?:=|IS)\s*(?:TRUE|true|'t'|1)\b",
    re.IGNORECASE,
)
_ALIAS_IS_CURRENT_FALSE = re.compile(
    r"\b(\w+)\.is_current\s*(?:=|IS)\s*(?:FALSE|false|'f'|0)\b",
    re.IGNORECASE,
)
_BARE_IS_CURRENT_FALSE = re.compile(
    r"\bis_current\s*(?:=|IS)\s*(?:FALSE|false|'f'|0)\b",
    re.IGNORECASE,
)
_WHERE_BOUNDARY = re.compile(
    r"\b(GROUP\s+BY|ORDER\s+BY|LIMIT|HAVING|UNION|OFFSET)\b",
    re.IGNORECASE,
)


class VersionRowIntent(str, Enum):
    CURRENT_ONLY = "current_only"
    HISTORY_ALLOWED = "history_allowed"


def classify_version_row_intent(question: str) -> VersionRowIntent:
    text = (question or "").strip()
    if not text:
        return VersionRowIntent.CURRENT_ONLY
    if _HISTORY_INTENT.search(text):
        return VersionRowIntent.HISTORY_ALLOWED
    return VersionRowIntent.CURRENT_ONLY


def versioned_table_short_names(grounding: "SchemaGrounding") -> set[str]:
    """Tables in the allowlist that expose an ``is_current`` column."""
    out: set[str] = set()
    for qualified, cols in (grounding.columns_by_table or {}).items():
        if not any(c.lower() == _IS_CURRENT_COL for c in cols):
            continue
        short = qualified.rsplit(".", 1)[-1].lower()
        out.add(short)
    return out


def _alias_has_current_predicate(sql: str, alias: str) -> bool:
    if _ALIAS_IS_CURRENT_PRED.search(sql):
        for m in _ALIAS_IS_CURRENT_PRED.finditer(sql):
            if m.group(1).lower() == alias.lower():
                return True
    return False


def _sql_allows_history_rows(sql: str) -> bool:
    if _BARE_IS_CURRENT_FALSE.search(sql):
        return True
    return bool(_ALIAS_IS_CURRENT_FALSE.search(sql))


def _predicates_for_sql(
    sql: str,
    versioned_tables: set[str],
) -> list[str]:
    aliases = alias_to_table_short(sql)
    preds: list[str] = []
    for alias, table_short in sorted(aliases.items()):
        if table_short not in versioned_tables:
            continue
        if _alias_has_current_predicate(sql, alias):
            continue
        preds.append(f"{alias}.{_IS_CURRENT_COL} IS TRUE")
    return preds


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


def apply_is_current_policy(
    sql: str,
    *,
    question: str,
    grounding: Optional["SchemaGrounding"] = None,
) -> tuple[str, bool]:
    """
    When intent is current-only, add ``alias.is_current IS TRUE`` for each
    versioned table in the query that lacks an explicit current predicate.

    Returns ``(sql, changed)``.
    """
    text = (sql or "").strip()
    if not text or text.upper() == "NONE":
        return sql, False
    if not re.match(r"(?is)^(WITH|SELECT)\b", text):
        return sql, False

    intent = classify_version_row_intent(question)
    if intent is VersionRowIntent.HISTORY_ALLOWED:
        logger.debug("is_current policy skipped (historical intent)")
        return sql, False
    if _sql_allows_history_rows(text):
        logger.debug("is_current policy skipped (SQL references non-current rows)")
        return sql, False
    if grounding is None or not grounding.columns_by_table:
        return sql, False

    versioned = versioned_table_short_names(grounding)
    if not versioned:
        return sql, False

    preds = _predicates_for_sql(text, versioned)
    if not preds:
        return sql, False

    out = _insert_where_predicates(text, preds)
    if out.strip() == text.strip():
        return sql, False

    logger.info(
        "Applied is_current filters (%s) for question intent=%s",
        ", ".join(preds),
        intent.value,
    )
    return out, True
