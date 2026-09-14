"""
Validate follow-up SQL edits preserve prior result columns unless user asked to drop them.
"""
from __future__ import annotations

import re
from typing import Optional

import sqlglot
from sqlglot import exp

from .intent_router import ChatIntent


_REMOVE_COL_RE = re.compile(
    r"\b(?:remove|drop|delete|omit|exclude|without|hide)\b.*\b(?:column|field)\b",
    re.I,
)
_REMOVE_NAMED_RE = re.compile(
    r"\b(?:remove|drop|delete|omit|exclude|without)\b(?:\s+the)?\s+([a-z][\w\s]{1,40}?)(?:\s+column|\s+field)?\b",
    re.I,
)
_START_OVER_RE = re.compile(
    r"\b(?:start\s+over|from\s+scratch|new\s+query|rewrite\s+from|ignore\s+(?:the\s+)?above)\b",
    re.I,
)


def _select_output_names(sql: str) -> list[str]:
    try:
        tree = sqlglot.parse_one(sql, dialect="postgres")
    except Exception:  # noqa: BLE001
        return []
    select = tree.find(exp.Select)
    if not select:
        return []
    names: list[str] = []
    for expr in select.expressions:
        if isinstance(expr, exp.Alias) and expr.alias:
            names.append(str(expr.alias).lower())
        elif isinstance(expr, exp.Column) and expr.name:
            names.append(str(expr.name).lower())
    return names


def check_refinement_preserves_sql(
    *,
    question: str,
    prior_sql: Optional[str],
    new_sql: Optional[str],
    chat_intent: ChatIntent,
) -> Optional[str]:
    """
    Return error if a refinement dropped columns the user did not ask to remove.
    """
    if chat_intent != ChatIntent.REFINE_SQL or not prior_sql or not new_sql:
        return None
    if _START_OVER_RE.search(question):
        return None

    prior_cols = set(_select_output_names(prior_sql))
    new_cols = set(_select_output_names(new_sql))
    if not prior_cols or not new_cols:
        return None

    removed = prior_cols - new_cols
    if not removed:
        return None

    if _REMOVE_COL_RE.search(question) or _REMOVE_NAMED_RE.search(question):
        return None

    # User asked to remove something specific — allow if removed set is small
    m = _REMOVE_NAMED_RE.search(question)
    if m:
        return None

    sample = ", ".join(sorted(removed)[:6])
    return (
        f"Follow-up SQL removed prior result column(s) ({sample}) without you asking "
        "to drop them. Edit the previous SQL in place — keep the same joins and columns "
        "unless you explicitly requested a removal."
    )
