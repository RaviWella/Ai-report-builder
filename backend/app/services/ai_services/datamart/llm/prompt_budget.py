"""Token budgeting and prompt clipping for datamart LLM calls."""
from __future__ import annotations

import logging
from collections.abc import Callable

from ..config import (
    CHARS_PER_TOKEN_EST,
    LLM_COMPLETION_RESERVE_TOKENS,
    LLM_CONTEXT_TOKEN_LIMIT,
    LLM_INPUT_TOKEN_BUDGET,
)

logger = logging.getLogger("ai_services.datamart.prompt")


def estimate_tokens(text: str) -> int:
    return max(1, int(len(text) / CHARS_PER_TOKEN_EST))


def is_context_length_error(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return (
        "maximum context length" in msg
        or "context length" in msg
        or "input length" in msg
        or ("max_tokens" in msg and "exceed" in msg)
    )


def clip_text(s: str, max_chars: int, label: str) -> str:
    if max_chars <= 0 or len(s) <= max_chars:
        return s
    return s[:max_chars].rstrip() + f"\n\n[{label} truncated]"


def history_context_tail(s: str, max_chars: int) -> str:
    if max_chars <= 0 or len(s) <= max_chars:
        return s
    return (
        "[Earlier conversation truncated — tail is most recent.]\n\n"
        + s[-max_chars:]
    )


def build_user_prompt_within_budget(
    system_prompt: str,
    question: str,
    history_text: str,
    schema_context: str,
    *,
    schema_cap: int,
    history_cap: int,
    build_user: Callable[[str, str], str],
) -> tuple[str, int]:
    """
    Shrink schema/history until system+user fit the model context window.
    Returns (user_prompt, estimated_total_input_tokens).
    """
    s_cap = min(len(schema_context), schema_cap)
    h_cap = min(len(history_text), history_cap)
    for _attempt in range(6):
        sc = clip_text(schema_context, s_cap, "schema")
        ht = history_context_tail(history_text, h_cap)
        user = build_user(sc, ht)
        est = estimate_tokens(system_prompt) + estimate_tokens(user)
        if est <= LLM_INPUT_TOKEN_BUDGET:
            if _attempt > 0:
                logger.info(
                    "Datamart prompt fit: schema_chars=%d history_chars=%d est_tokens=%d",
                    len(sc),
                    len(ht),
                    est,
                )
            return user, est
        over = est - LLM_INPUT_TOKEN_BUDGET
        cut = int(over * CHARS_PER_TOKEN_EST) + 250
        s_cap = max(1_200, s_cap - int(cut * 0.65))
        h_cap = max(300, h_cap - int(cut * 0.35))
    user = build_user(
        clip_text(schema_context, s_cap, "schema"),
        history_context_tail(history_text, h_cap),
    )
    est = estimate_tokens(system_prompt) + estimate_tokens(user)
    if est > LLM_INPUT_TOKEN_BUDGET:
        logger.warning(
            "Datamart prompt may exceed context (est_tokens=%d budget=%d)",
            est,
            LLM_INPUT_TOKEN_BUDGET,
        )
    return user, est


def context_limits_summary() -> dict[str, int]:
    return {
        "context_token_limit": LLM_CONTEXT_TOKEN_LIMIT,
        "completion_reserve_tokens": LLM_COMPLETION_RESERVE_TOKENS,
        "input_token_budget": LLM_INPUT_TOKEN_BUDGET,
    }
