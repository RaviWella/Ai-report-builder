"""Undo last continue_last modification — intent and mode guards."""
from app.services.ai_services.datamart.orchestration.intent_router import ChatIntent, classify_chat_intent
from app.services.ai_services.datamart.models import FollowUpMode


def test_follow_up_mode_new_question_forces_fresh_intent():
    sql = "SELECT a FROM public_mint_audit.dim_employee LIMIT 10;"
    intent = classify_chat_intent(
        "remove column x",
        last_sql=sql,
        has_prior_post_process=False,
        follow_up_mode=FollowUpMode.NEW_QUESTION,
    )
    assert intent == ChatIntent.NEW_QUERY


def test_follow_up_mode_continue_last_keeps_refine():
    sql = "SELECT a FROM public_mint_audit.dim_employee LIMIT 10;"
    intent = classify_chat_intent(
        "remove column x",
        last_sql=sql,
        has_prior_post_process=False,
        follow_up_mode=FollowUpMode.CONTINUE_LAST,
    )
    assert intent == ChatIntent.REFINE_SQL
