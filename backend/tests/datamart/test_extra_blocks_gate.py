"""Gate spurious ADDITIONAL_RESULT_BLOCKS unless the user asked for them."""
from app.services.ai_services.datamart.scenario.block_merge import should_execute_extra_result_blocks


def test_skip_extras_for_simple_leave_report():
    assert not should_execute_extra_result_blocks(
        "Generate a report of employees and their leave"
    )


def test_run_extras_when_user_asks_for_second_table():
    assert should_execute_extra_result_blocks(
        "Show employees and also include a second table for recruitment pipeline"
    )


def test_run_extras_for_add_scenario_follow_up():
    assert should_execute_extra_result_blocks(
        "filter to HQ only",
        follow_up_add_scenario=True,
    )
