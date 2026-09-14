"""Clarification turns: merge user replies and detect pending clarification state."""
from __future__ import annotations

import re
from typing import Any, Optional

from ..validation.validation_models import TrustLevel


def merge_clarified_question(anchor_question: str, clarification_reply: str) -> str:
    """
    Combine the original user question with their clarification answer.

    The merged string is re-run through the full retrieval + validation pipeline.
    """
    anchor = (anchor_question or "").strip()
    reply = (clarification_reply or "").strip()
    if not anchor:
        return reply
    if not reply:
        return anchor
    if reply.lower() in anchor.lower():
        return anchor
    return (
        f"{anchor}\n\n"
        f"Additional clarification from the user: {reply}"
    )


def validation_awaiting_clarification(validation: Optional[dict[str, Any]]) -> bool:
    if not validation or not isinstance(validation, dict):
        return False
    if validation.get("awaiting_clarification") is True:
        return True
    overall = validation.get("overall")
    if overall not in (TrustLevel.NEEDS_REVIEW.value, TrustLevel.BLOCKED.value):
        return False
    retrieval = validation.get("retrieval") or {}
    if isinstance(retrieval, dict):
        status = retrieval.get("status")
        if status in ("ambiguous", "insufficient"):
            return True
    gen = validation.get("generation")
    if isinstance(gen, dict) and gen.get("binding") == "failed":
        return True
    return False


def anchor_question_from_validation(
    validation: Optional[dict[str, Any]],
    *,
    fallback_user_question: Optional[str] = None,
) -> Optional[str]:
    if not validation or not isinstance(validation, dict):
        return fallback_user_question
    anchor = validation.get("anchor_question")
    if isinstance(anchor, str) and anchor.strip():
        return anchor.strip()
    return fallback_user_question


_CLARIFY_MARKERS = re.compile(
    r"\b(?:please clarify|to proceed|which of|could you|can you confirm|"
    r"need (?:a bit )?more detail|let me know)\b",
    re.IGNORECASE,
)


def looks_like_clarification_narrative(narrative: str) -> bool:
    text = (narrative or "").strip()
    if len(text) < 40:
        return False
    return bool(_CLARIFY_MARKERS.search(text))
