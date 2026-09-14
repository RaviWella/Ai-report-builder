"""Modify/refine turns must use full prompts (anchor SQL), not slim Tier C."""
from app.services.ai_services.datamart.orchestration.intent_router import ChatIntent
from app.services.ai_services.datamart.models import FollowUpMode
from app.services.ai_services.datamart.pipeline.prompt_builder import (
    build_chat_prompts_for_resolve,
)
from app.services.ai_services.datamart.pipeline.turn_setup import build_turn_setup


def test_modify_turn_uses_full_prompt_with_anchor():
    setup = build_turn_setup(
        question="please include the bank details into this",
        history_text="User: list employees\nAssistant: SQL:\nSELECT 1 FROM hr.mart_employee_current",
        follow_up_mode=FollowUpMode.CONTINUE_LAST,
        target_scenario_ids=None,
        previous_post_process_config=None,
        previous_primary_sql="SELECT m.emp_no FROM hr.mart_employee_current m LIMIT 10",
    )
    assert setup.is_modify
    system, user, _est = build_chat_prompts_for_resolve(
        setup,
        schema_context="TABLE mart_employee_current",
        use_tier_c_slim=True,
        anchor_sql=setup.anchor_sql,
        previous_primary_sql=None,
        previous_post_process_config=None,
        previous_extra_result_blocks=None,
    )
    assert "Modify mode" in user
    assert setup.anchor_sql and setup.anchor_sql in user
    assert setup.chat_intent == ChatIntent.REFINE_SQL
