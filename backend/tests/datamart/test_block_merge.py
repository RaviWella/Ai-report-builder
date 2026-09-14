"""Tests for extra_result_blocks merge on continue_last."""
from app.services.ai_services.datamart.scenario.block_merge import (
    merge_extra_result_blocks,
    user_wants_add_scenario,
)
from app.services.ai_services.datamart.models import DatamartResultBlock


def test_user_wants_add_scenario_detects_phrase():
    assert user_wants_add_scenario("Also add another scenario for Company B")
    assert not user_wants_add_scenario("Remove the salary column")


def test_merge_keeps_prior_blocks_on_continue_last():
    previous = [
        {
            "block_id": "blk-a",
            "title": "Scenario A",
            "sql_script": "SELECT 1",
            "post_process_config": None,
        }
    ]
    new = [
        DatamartResultBlock(
            block_id="blk-b",
            title="Scenario B",
            sql="SELECT 2",
        )
    ]
    merged = merge_extra_result_blocks(
        question="add another scenario for B",
        previous=previous,
        new_blocks=new,
        follow_up_continue=True,
    )
    assert merged is not None
    ids = {b["block_id"] for b in merged}
    assert ids == {"blk-a", "blk-b"}
