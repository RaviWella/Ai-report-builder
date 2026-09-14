"""Merge extra_result_blocks across continue_last refinements."""
from __future__ import annotations

import re
from typing import Any, Optional

from ..models import DatamartResultBlock

_REPLACE_ALL_EXTRAS = re.compile(
    r"\b(only|replace|instead of|remove (?:the )?other|drop (?:the )?other)\b",
    re.IGNORECASE,
)

_ADD_SCENARIO = re.compile(
    r"\b(?:another|second|additional|new|extra)\s+scenario\b"
    r"|\badd\s+(?:a\s+)?(?:another\s+)?(?:scenario|dataset|result\s+set)\b"
    r"|\b(?:also|and)\s+(?:include|show|add)\b.+\b(?:scenario|dataset|table|view)\b"
    r"|\bseparate\s+(?:table|result|query|dataset)\b"
    r"|\bcompare\b.+\b(?:to|with|and|versus|vs)\b",
    re.IGNORECASE,
)


def user_wants_add_scenario(question: str) -> bool:
    return bool(_ADD_SCENARIO.search(question or ""))


_EXTRA_BLOCKS_EXPLICIT = re.compile(
    r"\b(?:also|additionally|in addition)\b.+\b(?:show|include|add|display|run)\b"
    r"|\b(?:second|another|additional|separate)\s+(?:table|dataset|query|report|view|result)\b"
    r"|\b(?:compare|versus|vs\.?)\b.+\b(?:to|with|and)\b"
    r"|\bmultiple\s+(?:tables|datasets|reports|queries)\b"
    r"|\b(?:and|plus)\s+(?:a\s+)?(?:recruitment|payroll|attendance|leave)\b",
    re.IGNORECASE,
)


def should_execute_extra_result_blocks(
    question: str,
    *,
    follow_up_add_scenario: bool = False,
) -> bool:
    """
    Only run ADDITIONAL_RESULT_BLOCKS when the user asked for another dataset.

    The model often emits spurious extra SELECTs; executing them adds many slow LLM retries.
    """
    if follow_up_add_scenario:
        return True
    return bool(_EXTRA_BLOCKS_EXPLICIT.search(question or ""))


def user_wants_replace_all_extras(question: str) -> bool:
    return bool(_REPLACE_ALL_EXTRAS.search(question or ""))


def _block_to_stored(blk: DatamartResultBlock) -> dict[str, Any]:
    out: dict[str, Any] = {
        "block_id": blk.block_id,
        "title": blk.title,
        "sql_script": blk.sql or "",
        "post_process_config": blk.post_process_config,
    }
    if blk.validation:
        out["validation"] = blk.validation
    if blk.pipeline_trace is not None:
        out["pipeline_trace"] = blk.pipeline_trace.model_dump(mode="json")
    return out


def _stored_from_dict(blk: dict) -> dict[str, Any]:
    out: dict[str, Any] = {
        "block_id": str(blk.get("block_id") or ""),
        "title": blk.get("title"),
        "sql_script": blk.get("sql_script") or blk.get("sql") or "",
        "post_process_config": blk.get("post_process_config"),
    }
    if blk.get("validation"):
        out["validation"] = blk.get("validation")
    if blk.get("pipeline_trace"):
        out["pipeline_trace"] = blk.get("pipeline_trace")
    return out


def merge_extra_result_blocks(
    *,
    question: str,
    previous: Optional[list[dict]],
    new_blocks: Optional[list[DatamartResultBlock]],
    follow_up_continue: bool,
    target_scenario_ids: Optional[set[str]] = None,
) -> Optional[list[dict]]:
    """
    Combine prior assistant extras with new LLM extras on continue_last turns.

    - ``replace_all``: drop previous extras when user explicitly replaces them.
    - Otherwise keep prior blocks and upsert by ``block_id`` from new blocks.
    - When ``target_scenario_ids`` is set, only upsert extras whose block_id is listed
      (``primary`` is handled separately on the main SQL path).
    """
    from .scenario_scope import PRIMARY_SCENARIO_ID

    prev_list = [_stored_from_dict(b) for b in (previous or []) if isinstance(b, dict)]
    prev_list = [b for b in prev_list if b.get("block_id")]

    target_extra_ids: Optional[set[str]] = None
    if target_scenario_ids:
        target_extra_ids = {
            t for t in target_scenario_ids if t != PRIMARY_SCENARIO_ID
        }

    if not new_blocks:
        if follow_up_continue and not user_wants_replace_all_extras(question):
            return prev_list or None
        return None

    new_stored = [_block_to_stored(b) for b in new_blocks if b.sql]
    if target_extra_ids is not None:
        new_stored = [b for b in new_stored if b["block_id"] in target_extra_ids]

    if not follow_up_continue or user_wants_replace_all_extras(question):
        return new_stored or None

    by_id: dict[str, dict[str, Any]] = {b["block_id"]: b for b in prev_list}
    for blk in new_stored:
        if target_extra_ids is None or blk["block_id"] in target_extra_ids:
            by_id[blk["block_id"]] = blk
    merged = list(by_id.values())
    return merged or None
