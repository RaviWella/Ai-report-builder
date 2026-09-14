"""
Lightweight chat intent classification (no LLM).

Drives schema broker strategy: full discovery vs refine vs post-process-only.
"""
from __future__ import annotations

import re
from enum import Enum
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..models import FollowUpMode


class ChatIntent(str, Enum):
    NEW_QUERY = "new_query"
    REFINE_SQL = "refine_sql"
    POST_PROCESS_ONLY = "post_process_only"
    """Interpretive question about the prior result (yes/no, duplicates, explain the table)."""
    ANALYTICAL_OVER_PRIOR = "analytical_over_prior"


_POST_PROCESS_ONLY_PATTERNS = (
    r"\blabel\b",
    r"\bwording\b",
    r"\bsummary card\b",
    r"\baggregation_labels\b",
    r"\blabel_format\b",
    r"\bpost[- ]?process\b",
    r"\bappend_per_group\b",
    r"\bper[- ]group\b",
    r"\bunder the table\b",
    r"\bbelow the table\b",
    r"\bsummary row\b",
)

_REFINE_PATTERNS = (
    r"\badd column\b",
    r"\bremove column\b",
    r"\bremove the\b",
    r"\bdrop the\b",
    r"\bwithout\b",
    r"\bomit\b",
    r"\btake out\b",
    r"\bfrom the above\b",
    r"\babove response\b",
    r"\babove result\b",
    r"\bdrop column\b",
    r"\bfilter\b",
    r"\bwhere\b",
    r"\bsort\b",
    r"\border by\b",
    r"\blimit\b",
    r"\bjoin\b",
    r"\balso show\b",
    r"\bchange the query\b",
    r"\bmodify the (sql|query)\b",
    r"\bupdate the sql\b",
    r"\brename the\b",
    r"\brename\b.+\bcolumn\b",
    r"\bas\s+[\"']",
)

_PRIOR_RESULT_REF_PATTERNS = (
    r"\babove\b",
    r"\bprevious\b",
    r"\bprior\b",
    r"\bthat (table|result|list|report|answer)\b",
    r"\bthis (table|result|list)\b",
    r"\bthe (table|result|list) (above|shown)\b",
    r"\bin the (above|previous|prior)\b",
    r"\bfrom (that|this|the) (result|table)\b",
    r"\bwhat you (showed|returned|listed)\b",
    r"\blast (query|result|table|answer)\b",
)

_ANALYTICAL_SIGNAL_PATTERNS = (
    r"\bis\b.+\b(same|duplicate|duplicated|unique|identical)\b",
    r"\bare\b.+\b(same|duplicate|duplicated|unique|identical)\b",
    r"\bduplicat",
    r"\bhow many\b",
    r"\bwhat (percent|percentage|share)\b",
    r"\bcan you (confirm|explain|clarify|tell)\b",
    r"\bdoes (that|this|it) mean\b",
    r"\bis it true\b",
    r"\bwhy (is|are|does|do)\b",
    r"\bmeaning of\b",
    r"\binterpret\b",
    r"\bin plain (english|language)\b",
    r"\?\s*$",
)


def classify_chat_intent(
    question: str,
    *,
    last_sql: Optional[str],
    has_prior_post_process: bool,
    follow_up_mode: Optional["FollowUpMode"] = None,
) -> ChatIntent:
    """
    Classify the user message for broker + prompt strategy.

    Parameters
    ----------
    last_sql:
        SQL from the previous assistant turn in this session (if any).
    has_prior_post_process:
        Whether the session already has POST_PROCESS steps on the last turn.
    follow_up_mode:
        Explicit user choice from the UI. ``new_question`` always starts fresh;
        ``continue_last`` keeps refinement / analytical follow-up behaviour.
    """
    if follow_up_mode is not None:
        from ..models import FollowUpMode

        if follow_up_mode == FollowUpMode.NEW_QUESTION:
            return ChatIntent.NEW_QUERY
        if follow_up_mode == FollowUpMode.CLARIFY_REPLY:
            return ChatIntent.NEW_QUERY
        if follow_up_mode == FollowUpMode.ADD_SCENARIO:
            return ChatIntent.NEW_QUERY
        if follow_up_mode == FollowUpMode.CONTINUE_LAST:
            if not last_sql:
                return ChatIntent.NEW_QUERY
            q = question.lower().strip()
            if _looks_like_post_process_only(q, has_prior_post_process):
                return ChatIntent.POST_PROCESS_ONLY
            if _looks_analytical_over_prior(q):
                return ChatIntent.ANALYTICAL_OVER_PRIOR
            return ChatIntent.REFINE_SQL

    q = question.lower().strip()
    if not last_sql:
        return ChatIntent.NEW_QUERY

    if _looks_like_post_process_only(q, has_prior_post_process):
        return ChatIntent.POST_PROCESS_ONLY

    if any(re.search(p, q) for p in _REFINE_PATTERNS):
        return ChatIntent.REFINE_SQL

    if has_prior_post_process and any(re.search(p, q) for p in _POST_PROCESS_ONLY_PATTERNS):
        return ChatIntent.POST_PROCESS_ONLY

    if _looks_analytical_over_prior(q):
        return ChatIntent.ANALYTICAL_OVER_PRIOR

    return ChatIntent.REFINE_SQL


def _looks_analytical_over_prior(question: str) -> bool:
    """Follow-up that needs a direct textual answer about the prior result, not only a new grid."""
    sql_edit_signals = (
        "remove ",
        "drop ",
        "add column",
        "omit ",
        "without ",
        "rename ",
        "update the sql",
        "modify the sql",
        "change the query",
        "order by",
        "sort by",
        "limit ",
    )
    if any(s in question for s in sql_edit_signals):
        return False

    refers_prior = any(re.search(p, question) for p in _PRIOR_RESULT_REF_PATTERNS)
    analytical = any(re.search(p, question) for p in _ANALYTICAL_SIGNAL_PATTERNS)

    if refers_prior and analytical:
        return True

    # "is the same employee duplicated" without explicit "above" still targets prior context.
    if analytical and re.search(r"\bduplicat", question):
        return True

    if refers_prior and "?" in question and not re.search(
        r"\b(prepare|generate|build|create)\b.+\breport\b", question
    ):
        return True

    return False


def _looks_like_post_process_only(question: str, has_prior_post_process: bool) -> bool:
    sql_change_signals = (
        "select ",
        "from ",
        "new table",
        "different employees",
        "all employees",
        "workforce report",
        "generate a report",
    )
    if any(s in question for s in sql_change_signals):
        return False
    if not any(re.search(p, question) for p in _POST_PROCESS_ONLY_PATTERNS):
        return False
    return has_prior_post_process or "append" in question or "summary" in question
