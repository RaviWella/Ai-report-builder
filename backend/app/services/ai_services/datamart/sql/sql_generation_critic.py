"""Optional LLM critic pass: does generated SQL answer the question using grounded context?"""
from __future__ import annotations

import logging
import re
from typing import Optional

from ..llm.llm_client import LlmRole, call_llm
from ..schema_broker import SchemaGrounding

logger = logging.getLogger("ai_services.datamart.critic")

_CRITIC_SYSTEM = """You are a SQL reviewer for an HR analytics warehouse.
Given the user question, grounded schema summary, and PostgreSQL SQL, list issues only.
Reply with exactly one line:
VERDICT: OK
or
VERDICT: FIX
ISSUES:
- <short bullet>
Keep under 5 bullets. Do not rewrite the full SQL."""


def run_sql_generation_critic(
    *,
    question: str,
    sql: str,
    grounding: SchemaGrounding,
    schema_summary: str,
) -> tuple[bool, list[str]]:
    """
    Return (ok, warning_messages). On LLM failure, returns (True, []) — non-blocking.
    """
    user = (
        f"QUESTION:\n{question}\n\n"
        f"GROUNDED SCHEMA (summary):\n{schema_summary[:3500]}\n\n"
        f"SQL:\n```sql\n{sql}\n```"
    )
    try:
        raw = call_llm(_CRITIC_SYSTEM, user, role=LlmRole.REPAIR)
    except Exception as exc:  # noqa: BLE001
        logger.warning("SQL critic LLM failed (non-fatal): %s", exc)
        return True, []

    text = (raw or "").strip()
    if re.search(r"VERDICT:\s*OK\b", text, re.IGNORECASE):
        return True, []
    issues: list[str] = []
    in_issues = False
    for line in text.splitlines():
        if re.match(r"VERDICT:\s*FIX", line, re.IGNORECASE):
            in_issues = True
            continue
        if in_issues and line.strip().startswith("-"):
            issues.append(line.strip().lstrip("-").strip())
    if not issues and "FIX" in text.upper():
        issues.append("Critic flagged SQL as not fully answering the question.")
    return False, issues[:5]
