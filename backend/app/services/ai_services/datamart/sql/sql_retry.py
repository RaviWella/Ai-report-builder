"""LLM retry helper when SQL execution or validation fails."""
from __future__ import annotations

import logging
from typing import Optional

from ..prompts.chat_prompts import CHAT_RETRY_PROMPT_TEMPLATE
from ..llm.llm_client import LlmRole, call_llm
from ..llm.llm_response import extract_narrative, extract_post_process_config, extract_sql

logger = logging.getLogger("ai_services.datamart.sql_retry")


def retry_on_error(
    system_prompt: str,
    sql: str,
    error: str,
    narrative: str,
    post_process_config: Optional[list[dict]],
) -> tuple[str, str, Optional[list[dict]], Optional[str]]:
    retry_prompt = CHAT_RETRY_PROMPT_TEMPLATE.format(error=error, sql=sql)
    try:
        fixed_output = call_llm(system_prompt, retry_prompt, role=LlmRole.REPAIR)
        fixed_sql = extract_sql(fixed_output) or sql
        fixed_narrative = extract_narrative(fixed_output)
        fixed_ppc = extract_post_process_config(fixed_output)
        if fixed_ppc is None:
            fixed_ppc = post_process_config
        logger.info("LLM produced a fixed SQL after error")
        return fixed_sql, fixed_narrative, fixed_ppc, None
    except Exception as exc:  # noqa: BLE001
        logger.error("Retry LLM call failed: %s", exc)
        return sql, narrative, post_process_config, str(exc)
