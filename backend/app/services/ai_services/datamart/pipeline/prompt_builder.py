"""Build system and user prompts for chat turns."""
from __future__ import annotations

from typing import Callable, Optional

from ..prompts.chat_prompts import (
    CHAT_USER_PROMPT_TEMPLATE,
    format_add_scenario_addon,
    format_analytical_intent_addon,
    format_chat_system_prompt,
    format_new_question_in_session_addon,
    format_refinement_anchor_block,
    format_tier_c_system_prompt,
    format_tier_c_user_prompt,
)
from .. import config as dm_config
from ..orchestration.modify_mode import format_continue_last_modify_addon
from ..scenario.scenario_scope import format_target_scenario_addon
from ..orchestration.intent_router import ChatIntent
from ..config import BROKER_MAX_PROMPT_CHARS, CHAT_HISTORY_MAX_CHARS
from ..llm.prompt_budget import build_user_prompt_within_budget
from .turn_setup import ChatTurnSetup


def build_chat_prompts(
    setup: ChatTurnSetup,
    *,
    schema_context: str,
    anchor_sql: Optional[str],
    previous_primary_sql: Optional[str],
    previous_post_process_config: Optional[list],
    previous_extra_result_blocks: Optional[list],
) -> tuple[str, str, int]:
    system_prompt = format_chat_system_prompt()

    def _build_main_user(sc: str, ht: str) -> str:
        core = CHAT_USER_PROMPT_TEMPLATE.format(
            schema_context=sc,
            history_text=ht,
            question=setup.question,
        )
        if setup.is_new_question or setup.is_add_scenario or setup.targets:
            anchor = ""
        else:
            anchor = format_refinement_anchor_block(anchor_sql or setup.last_sql)
        addon = ""
        if setup.is_new_question:
            addon += format_new_question_in_session_addon()
        if setup.is_modify and not setup.is_add_scenario and not setup.is_new_question:
            addon += format_continue_last_modify_addon()
        if setup.targets and not setup.is_add_scenario and not setup.is_new_question:
            addon += format_target_scenario_addon(
                setup.targets,
                primary_sql=previous_primary_sql or anchor_sql or setup.last_sql,
                primary_post_process=previous_post_process_config,
                extra_blocks=previous_extra_result_blocks,
            )
        if setup.is_add_scenario:
            addon += format_add_scenario_addon()
        elif setup.chat_intent == ChatIntent.ANALYTICAL_OVER_PRIOR:
            addon += format_analytical_intent_addon()
        return core + anchor + addon

    user_prompt, est = build_user_prompt_within_budget(
        system_prompt,
        setup.question,
        setup.history_text,
        schema_context,
        schema_cap=BROKER_MAX_PROMPT_CHARS,
        history_cap=CHAT_HISTORY_MAX_CHARS,
        build_user=_build_main_user,
    )
    return system_prompt, user_prompt, est


def build_tier_c_prompts(
    setup: ChatTurnSetup,
    *,
    schema_context: str,
) -> tuple[str, str, int]:
    """Compact prompts for Tier C only (small models, reduced truncation)."""
    system_prompt = format_tier_c_system_prompt()
    user_prompt = format_tier_c_user_prompt(
        schema_context=schema_context,
        history_text=setup.history_text or "",
        question=setup.question,
    )
    from ..llm.prompt_budget import estimate_tokens

    est = estimate_tokens(system_prompt) + estimate_tokens(user_prompt)
    return system_prompt, user_prompt, est


def build_chat_prompts_for_resolve(
    setup: ChatTurnSetup,
    *,
    schema_context: str,
    use_tier_c_slim: bool,
    anchor_sql: Optional[str],
    previous_primary_sql: Optional[str],
    previous_post_process_config: Optional[list],
    previous_extra_result_blocks: Optional[list],
) -> tuple[str, str, int]:
    """Choose full chat prompts vs slim Tier-C prompts based on config."""
    # Modify/refine turns need anchor SQL and modify instructions — never slim Tier C.
    if setup.is_modify or setup.chat_intent in (
        ChatIntent.REFINE_SQL,
        ChatIntent.POST_PROCESS_ONLY,
    ):
        return build_chat_prompts(
            setup,
            schema_context=schema_context,
            anchor_sql=anchor_sql,
            previous_primary_sql=previous_primary_sql,
            previous_post_process_config=previous_post_process_config,
            previous_extra_result_blocks=previous_extra_result_blocks,
        )
    if use_tier_c_slim and dm_config.DATAMART_TIER_C_SLIM_PROMPT:
        return build_tier_c_prompts(setup, schema_context=schema_context)
    return build_chat_prompts(
        setup,
        schema_context=schema_context,
        anchor_sql=anchor_sql,
        previous_primary_sql=previous_primary_sql,
        previous_post_process_config=previous_post_process_config,
        previous_extra_result_blocks=previous_extra_result_blocks,
    )
