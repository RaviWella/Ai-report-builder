"""Parse structured datamart LLM responses (NARRATIVE / SQL / POST_PROCESS)."""
from __future__ import annotations

import json
import logging
import re
from typing import Optional

import sqlglot

logger = logging.getLogger("ai_services.datamart.llm_response")

_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")


def strip_ansi_escapes(text: str) -> str:
    """Remove terminal color/underline codes sometimes echoed into LLM SQL."""
    return _ANSI_ESCAPE_RE.sub("", text)


def extract_last_sql_from_history(history_text: str) -> Optional[str]:
    blocks = re.findall(
        r"```sql\s*([\s\S]+?)```",
        history_text,
        re.IGNORECASE,
    )
    if not blocks:
        return None
    return blocks[-1].strip()


def is_stub_sql(sql: Optional[str]) -> bool:
    """
    True for placeholder SELECTs that must not run (0-row guards, tautologies).
    """
    if not sql or not str(sql).strip():
        return False
    body = str(sql).strip().rstrip(";").strip()
    low = body.lower()
    if re.search(r"\bwhere\s+(?:false|1\s*=\s*0|0\s*=\s*1)\b", low):
        return True
    if re.search(r"\band\s+(?:false|1\s*=\s*0)\b", low):
        return True
    if re.match(r"(?is)^select\s+1\s+where\s+false", low):
        return True
    if re.match(r"(?is)^select\s+null\s+where\s+false", low):
        return True
    # Single constant projection with no real table reference
    if re.match(r"(?is)^select\s+(?:1|null)\s*(?:where\s+false)?\s*$", low):
        return True
    return False


def is_non_executable_sql(sql: Optional[str]) -> bool:
    """True when SQL must not be sent to the warehouse (NONE, empty, non-SELECT, stub)."""
    if not sql or not str(sql).strip():
        return True
    body = str(sql).strip()
    if re.match(r"(?is)^NONE\s*;?\s*$", body):
        return True
    if is_stub_sql(body):
        return True
    return not re.match(r"(?is)^(WITH|SELECT)\b", body)


def normalize_executable_sql(sql: Optional[str]) -> Optional[str]:
    """Return SQL suitable for execution, or None if missing / NONE / invalid shape."""
    if is_non_executable_sql(sql):
        return None
    return strip_ansi_escapes(str(sql).strip())


def extract_sql(llm_response: str) -> Optional[str]:
    for m in re.finditer(
        r"```[a-zA-Z0-9_-]*\s*([\s\S]*?)```",
        llm_response,
        re.IGNORECASE,
    ):
        body = m.group(1).strip()
        if not body:
            continue
        if re.match(r"(?is)^NONE\s*$", body):
            continue
        if re.match(r"(?is)^(WITH|SELECT)\b", body):
            return body

    if re.search(r"SQL:\s*\n\s*NONE\b", llm_response, re.IGNORECASE):
        return None

    # SQL: section without a fenced block (common when the model skips ```sql)
    sql_section = re.search(
        r"SQL:\s*\n+(?:```[a-zA-Z0-9_-]*\s*\n)?([\s\S]*?)"
        r"(?=\n\s*POST_PROCESS\b|\n\s*ADDITIONAL_RESULT_BLOCKS\b|\n\s*NARRATIVE\b|\Z)",
        llm_response,
        re.IGNORECASE,
    )
    if sql_section:
        body = sql_section.group(1).strip()
        body = re.sub(r"\n```\s*$", "", body).strip()
        if body and not re.match(r"(?is)^NONE\s*$", body):
            if re.match(r"(?is)^(WITH|SELECT)\b", body):
                return body

    cte = re.search(r"(WITH\s+\w+[\s\S]+?;)", llm_response, re.IGNORECASE)
    if cte:
        return cte.group(1).strip()

    select = re.search(r"(SELECT[\s\S]+?;)", llm_response, re.IGNORECASE)
    if select:
        return select.group(1).strip()
    select_loose = re.search(
        r"(SELECT[\s\S]+?)(?=\n\s*POST_PROCESS\b|\n\s*ADDITIONAL_RESULT_BLOCKS\b|```|\Z)",
        llm_response,
        re.IGNORECASE,
    )
    if select_loose:
        return select_loose.group(1).strip()

    return None


def extract_narrative(llm_response: str) -> str:
    match = re.search(
        r"NARRATIVE:\s*(?:\n\s*)?(.*?)(?=\n\s*SQL:|\n\s*ADDITIONAL_RESULT_BLOCKS\b|\Z)",
        llm_response,
        re.IGNORECASE | re.DOTALL,
    )
    if match:
        text = match.group(1).strip()
        if text:
            return text
    return "Here are the results based on your question."


def extract_post_process_config(llm_response: str) -> Optional[list[dict]]:
    match = re.search(
        r"POST_PROCESS[^\n]*(?:\n\s*)?```(?:json)?\s*(\[[\s\S]+?\])\s*```",
        llm_response,
        re.IGNORECASE,
    )
    if not match:
        return None
    try:
        config = json.loads(match.group(1))
        if not isinstance(config, list):
            logger.warning("POST_PROCESS block is not a JSON array — ignoring")
            return None
        return config
    except json.JSONDecodeError as exc:
        logger.warning("POST_PROCESS JSON parse failed: %s", exc)
        return None


def extract_additional_result_blocks(llm_response: str) -> list[dict]:
    match = re.search(
        r"ADDITIONAL_RESULT_BLOCKS[^\n]*(?:\n\s*)?```(?:json)?\s*(\[[\s\S]+?\])\s*```",
        llm_response,
        re.IGNORECASE,
    )
    if not match:
        return []
    try:
        raw = json.loads(match.group(1))
        if not isinstance(raw, list):
            return []
        return [x for x in raw if isinstance(x, dict)]
    except json.JSONDecodeError as exc:
        logger.warning("ADDITIONAL_RESULT_BLOCKS JSON parse failed: %s", exc)
        return []


def merge_post_process_configs(
    previous: Optional[list[dict]],
    new: Optional[list[dict]],
) -> Optional[list[dict]]:
    if not new and not previous:
        return None
    if not new:
        return None
    if not previous:
        return new
    n_prev, n_new = len(previous), len(new)
    if n_new >= n_prev and new[:n_prev] == previous:
        return new
    if n_new < n_prev and new == previous[:n_prev]:
        return new
    return previous + new


def validate_sql_syntax(sql: str) -> Optional[str]:
    if is_non_executable_sql(sql):
        return "SQL is missing or set to NONE; a SELECT query is required."
    try:
        sqlglot.parse_one(sql, dialect="postgres")
        return None
    except Exception as exc:  # noqa: BLE001
        return str(exc)


def build_history_text(history: list[dict]) -> str:
    if not history:
        return "(No previous messages)"
    lines = []
    for msg in history[-6:]:
        role = msg.get("role", "user").capitalize()
        content = msg.get("content", "")
        lines.append(f"{role}: {content}")
    return "\n".join(lines)
