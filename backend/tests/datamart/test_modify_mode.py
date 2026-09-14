"""Modify (continue_last) vs add-scenario mode helpers."""
from app.services.ai_services.datamart.orchestration.intent_router import ChatIntent, classify_chat_intent
from app.services.ai_services.datamart.orchestration.modify_mode import (
    check_modify_sql_anchored,
    is_modify_turn,
    resolve_anchor_sql,
    should_skip_deterministic_sql_shortcuts,
)
from app.services.ai_services.datamart.models import FollowUpMode


def test_is_modify_turn_continue_last():
    assert is_modify_turn(
        FollowUpMode.CONTINUE_LAST,
        is_new_question=False,
        is_add_scenario=False,
    )


def test_is_modify_turn_not_add_scenario():
    assert not is_modify_turn(
        FollowUpMode.ADD_SCENARIO,
        is_new_question=False,
        is_add_scenario=True,
    )


def test_resolve_anchor_sql_primary_only():
    sql = resolve_anchor_sql(
        previous_primary_sql="SELECT 1 FROM hr.mart_employee_current",
        last_sql="SELECT 9",
        targets={"primary"},
    )
    assert "mart_employee_current" in (sql or "")


def test_resolve_anchor_sql_skips_when_only_extra_targeted():
    assert (
        resolve_anchor_sql(
            previous_primary_sql="SELECT 1",
            last_sql="SELECT 1",
            targets={"block-b"},
        )
        is None
    )


def test_skip_deterministic_shortcuts_for_modify():
    assert should_skip_deterministic_sql_shortcuts(
        is_modify=True,
        is_add_scenario=False,
        targets=None,
    )


def test_classify_continue_last_defaults_to_refine():
    intent = classify_chat_intent(
        "remove the department column",
        last_sql="SELECT a, b FROM hr.mart_employee_current LIMIT 10",
        has_prior_post_process=False,
        follow_up_mode=FollowUpMode.CONTINUE_LAST,
    )
    assert intent == ChatIntent.REFINE_SQL


def test_check_modify_sql_anchored_rejects_unrelated_tables():
    err = check_modify_sql_anchored(
        anchor_sql="SELECT e.full_name FROM hr.mart_employee_current e LIMIT 10",
        new_sql="SELECT p.amount FROM hr.vw_payroll_summary p LIMIT 10",
    )
    assert err is not None
    assert "Modify mode" in err
