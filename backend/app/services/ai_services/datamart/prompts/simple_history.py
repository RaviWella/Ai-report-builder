"""
Shape session history for the simplified datamart agent by follow-up mode.

Avoids dumping every prior SQL/scenario into the LLM prompt (main cause of confusion).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from ..models import FollowUpMode
from ..orchestration.modify_mode import format_continue_last_modify_addon, is_modify_turn, resolve_anchor_sql
from ..scenario.scenario_scope import normalize_target_scenario_ids
from ..llm.llm_response import extract_last_sql_from_history

_SUMMARY_PREFIX = "[Summary of earlier conversation]"
_SQL_BLOCK = re.compile(r"```sql\s*[\s\S]*?```", re.IGNORECASE)
_EXTRA_DATASET = re.compile(
    r"\[Additional dataset:[^\]]+\][\s\S]*?(?=\n\n(?:User:|Assistant:|\[)|\Z)",
    re.MULTILINE,
)
_POST_PROCESS = re.compile(
    r"\[POST_PROCESS[^\]]*\][\s\S]*?```json[\s\S]*?```",
    re.IGNORECASE,
)


@dataclass
class SimpleTurnContext:
    """Prompt inputs derived from session + follow-up mode."""

    history_for_prompt: str
    mode_instructions: str
    anchor_sql: Optional[str]
    is_modify: bool
    is_add_scenario: bool
    is_new_question: bool


def _split_summary_and_body(history_text: str) -> tuple[str, str]:
    raw = (history_text or "").strip()
    if not raw or raw == "(No previous messages)":
        return "", ""
    if raw.startswith(_SUMMARY_PREFIX):
        parts = raw.split("\n", 1)
        if len(parts) == 2:
            return parts[0].strip(), parts[1].strip()
    return "", raw


def _strip_sql_and_blocks(text: str) -> str:
    out = _SQL_BLOCK.sub("[prior SQL omitted]", text)
    out = _EXTRA_DATASET.sub("[prior additional dataset omitted]", out)
    out = _POST_PROCESS.sub("", out)
    out = re.sub(r"\[SQL turn \d+\]\s*\[prior SQL omitted\]", "[prior SQL omitted]", out)
    return re.sub(r"\n{3,}", "\n\n", out).strip()


def _last_turn_dialogue(body: str) -> str:
    """Keep only the last user message and assistant narrative (no SQL)."""
    if not body.strip():
        return "(No prior turn)"
    chunks = re.split(r"(?=^User:\s)", body, flags=re.MULTILINE)
    chunks = [c.strip() for c in chunks if c.strip()]
    if not chunks:
        return _strip_sql_and_blocks(body)
    last = chunks[-1]
    # Drop assistant SQL sections after narrative line
    lines = last.splitlines()
    kept: list[str] = []
    for line in lines:
        if line.startswith("[SQL turn") or line.startswith("```sql"):
            break
        if line.startswith("[POST_PROCESS") or line.startswith("[Additional dataset"):
            break
        kept.append(line)
    return "\n".join(kept).strip() or _strip_sql_and_blocks(last)


def _new_question_history(history_text: str) -> str:
    summary, body = _split_summary_and_body(history_text)
    parts: list[str] = []
    if summary:
        parts.append(summary)
    if body:
        parts.append(
            _strip_sql_and_blocks(body)
            + "\n\n(Previous SQL omitted — write a **new** query for the current question only.)"
        )
    return "\n\n".join(parts) if parts else "(No previous messages)"


def _modify_mode_history(history_text: str) -> str:
    summary, body = _split_summary_and_body(history_text)
    parts: list[str] = []
    if summary:
        parts.append(summary)
    parts.append(_last_turn_dialogue(body))
    return "\n\n".join(parts)


def _add_scenario_history(history_text: str) -> str:
    """Strip prior SQL so the model does not merge scenarios (simple SQL output mode)."""
    raw = (history_text or "").strip()
    if not raw or raw == "(No previous messages)":
        return "(Prior scenarios are stored on the server — only answer the new question.)"
    summary, body = _split_summary_and_body(raw)
    stripped = _strip_sql_and_blocks(body)
    parts: list[str] = []
    if summary:
        parts.append(summary)
    if stripped:
        parts.append(stripped)
    return "\n\n".join(parts) if parts else "(Prior scenarios stored on server.)"


_ADD_SCENARIO_SIMPLE = """
## Add scenario mode
The user already has a report (primary table + any prior scenarios). Answer **only** the latest question.
Output **one** new SELECT in a ```sql``` block. Do **not** rewrite prior scenario SQL — the server keeps them unchanged.
"""


def _legacy_is_continue(
    follow_up_mode: Optional[FollowUpMode],
    *,
    previous_primary_sql: Optional[str],
    previous_extra_result_blocks: Optional[list],
    previous_post_process_config: Optional[list],
) -> bool:
    if follow_up_mode is not None:
        return False
    return bool(
        previous_primary_sql
        or previous_extra_result_blocks
        or previous_post_process_config
    )


def prepare_simple_turn_context(
    *,
    question: str,
    history_text: str,
    follow_up_mode: Optional[FollowUpMode],
    previous_primary_sql: Optional[str] = None,
    previous_post_process_config: Optional[list] = None,
    previous_extra_result_blocks: Optional[list] = None,
    target_scenario_ids: Optional[list[str]] = None,
) -> SimpleTurnContext:
    del question  # reserved for future target-scenario anchoring
    targets = normalize_target_scenario_ids(target_scenario_ids)
    is_new_question = follow_up_mode == FollowUpMode.NEW_QUESTION
    is_add_scenario = follow_up_mode == FollowUpMode.ADD_SCENARIO
    if follow_up_mode is None and _legacy_is_continue(
        follow_up_mode,
        previous_primary_sql=previous_primary_sql,
        previous_extra_result_blocks=previous_extra_result_blocks,
        previous_post_process_config=previous_post_process_config,
    ):
        is_new_question = False

    is_modify = is_modify_turn(
        follow_up_mode,
        is_new_question=is_new_question,
        is_add_scenario=is_add_scenario,
    ) or (
        follow_up_mode is None
        and not is_new_question
        and not is_add_scenario
    )

    last_sql = extract_last_sql_from_history(history_text)
    anchor_sql = (
        resolve_anchor_sql(
            previous_primary_sql=previous_primary_sql,
            last_sql=last_sql,
            targets=targets or None,
        )
        if is_modify
        else None
    )

    mode_instructions = ""
    if is_add_scenario:
        history_for_prompt = _add_scenario_history(history_text)
        mode_instructions = _ADD_SCENARIO_SIMPLE.strip()
    elif is_modify:
        history_for_prompt = _modify_mode_history(history_text)
        mode_instructions = format_continue_last_modify_addon()
        if anchor_sql:
            mode_instructions += (
                f"\n\n## Anchored SQL (edit this query in place)\n```sql\n{anchor_sql.strip()}\n```"
            )
    elif is_new_question:
        history_for_prompt = _new_question_history(history_text)
        mode_instructions = (
            "Treat this as a **new standalone question**. "
            "Do not reuse or extend SQL from earlier turns unless the user explicitly asks."
        )
    else:
        history_for_prompt = history_text.strip() or "(No previous messages)"

    return SimpleTurnContext(
        history_for_prompt=history_for_prompt,
        mode_instructions=mode_instructions,
        anchor_sql=anchor_sql,
        is_modify=is_modify,
        is_add_scenario=is_add_scenario,
        is_new_question=is_new_question,
    )
