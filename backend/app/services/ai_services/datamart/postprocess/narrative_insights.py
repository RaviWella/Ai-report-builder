"""
Deterministic narrative enrichment after SQL runs (analytical follow-ups).
"""
from __future__ import annotations

import re
from typing import Any, Optional

from ..orchestration.intent_router import ChatIntent

_VERDICT_PREFIX = re.compile(
    r"^(yes|no|partially|correct|incorrect|indeed|not quite)\b",
    re.IGNORECASE,
)


def _col_index(columns: list[str], *hints: str) -> Optional[int]:
    lowers = [c.lower() for c in columns]
    for hint in hints:
        h = hint.lower()
        for i, c in enumerate(lowers):
            if h in c or c == h:
                return i
    return None


def _as_number(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _insight_for_duplicate_question(
    question: str,
    columns: list[str],
    rows: list[list[Any]],
) -> Optional[str]:
    if "duplicat" not in question.lower():
        return None
    n = len(rows)
    if n == 0:
        return (
            "No — based on the query, no employees appear in more than one matching "
            "record (the result set is empty)."
        )
    count_idx = _col_index(columns, "record_count", "count", "cnt", "duplicate")
    if count_idx is not None:
        counts = [_as_number(r[count_idx]) for r in rows if count_idx < len(r)]
        counts = [c for c in counts if c is not None]
        if counts and all(c <= 1 for c in counts):
            return (
                "No — every row in the result has a count of 1 or less, so employees "
                "are not duplicated under this definition."
            )
        max_c = max(counts) if counts else None
        max_part = f" (up to {int(max_c)} records per employee)" if max_c and max_c > 1 else ""
        return (
            f"Yes — {n:,} employee{'s' if n != 1 else ''} appear in more than one "
            f"matching row{max_part}. The table lists each such employee with their "
            f"duplicate count."
        )
    return (
        f"Yes — {n:,} row{'s' if n != 1 else ''} in the result indicate employees "
        f"that match the duplicate criteria from your question."
    )


def _insight_for_count_question(
    question: str,
    columns: list[str],
    rows: list[list[Any]],
) -> Optional[str]:
    q = question.lower()
    if "how many" not in q and "count of" not in q and "number of" not in q:
        return None
    n = len(rows)
    if n == 1 and len(columns) <= 3:
        parts: list[str] = []
        for i, col in enumerate(columns):
            val = rows[0][i] if i < len(rows[0]) else None
            num = _as_number(val)
            if num is not None:
                label = col.replace("_", " ")
                parts.append(f"{label}: {num:,.0f}".replace(".0", ""))
        if parts:
            return "Answer: " + "; ".join(parts) + "."
    if n > 0:
        return f"The query returned {n:,} row{'s' if n != 1 else ''}."
    return "The query returned no rows."


def enrich_narrative_from_results(
    *,
    question: str,
    narrative: str,
    columns: list[str],
    rows: list[list[Any]],
    intent: ChatIntent,
) -> str:
    """
    Prepend a concise verdict or headline metric when the model narrative is thin.
    """
    if intent != ChatIntent.ANALYTICAL_OVER_PRIOR:
        return narrative
    if not columns:
        return narrative

    body = (narrative or "").strip()
    if body and _VERDICT_PREFIX.match(body):
        return narrative

    insight = _insight_for_duplicate_question(question, columns, rows)
    if not insight:
        insight = _insight_for_count_question(question, columns, rows)

    if not insight:
        if rows:
            insight = (
                f"Based on the executed query, there are {len(rows):,} result "
                f"row{'s' if len(rows) != 1 else ''} (see table below)."
            )
        else:
            insight = "The executed query returned no rows for this question."

    if not body:
        return insight
    if insight.lower() in body.lower():
        return narrative
    return f"{insight}\n\n{body}"
