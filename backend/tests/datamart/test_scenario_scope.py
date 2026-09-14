"""Tests for targeted multi-scenario modify scope."""
from app.services.ai_services.datamart.scenario.block_merge import merge_extra_result_blocks
from app.services.ai_services.datamart.models import DatamartResultBlock
from app.services.ai_services.datamart.scenario.scenario_scope import (
    PRIMARY_SCENARIO_ID,
    format_target_scenario_addon,
    normalize_target_scenario_ids,
)


def test_normalize_target_scenario_ids_dedupes():
    assert normalize_target_scenario_ids(["primary", " block-a ", "block-a"]) == {
        "primary",
        "block-a",
    }


def test_format_target_scenario_addon_lists_only_selected():
    addon = format_target_scenario_addon(
        {"block-b"},
        primary_sql="SELECT 1",
        primary_post_process=None,
        extra_blocks=[
            {"block_id": "block-a", "title": "A", "sql_script": "SELECT a"},
            {"block_id": "block-b", "title": "B", "sql_script": "SELECT b"},
        ],
    )
    assert "block-b" in addon
    assert "block-a" not in addon or "block_id=block-a" not in addon


def test_merge_extra_blocks_only_upserts_target_ids():
    previous = [
        {"block_id": "keep-me", "title": "Old", "sql_script": "SELECT old"},
        {"block_id": "change-me", "title": "Old2", "sql_script": "SELECT old2"},
    ]
    new_blocks = [
        DatamartResultBlock(
            block_id="change-me",
            title="New2",
            sql="SELECT new2",
        ),
        DatamartResultBlock(
            block_id="stray",
            title="Stray",
            sql="SELECT stray",
        ),
    ]
    merged = merge_extra_result_blocks(
        question="tweak scenario 2",
        previous=previous,
        new_blocks=new_blocks,
        follow_up_continue=True,
        target_scenario_ids={"change-me"},
    )
    assert merged is not None
    by_id = {b["block_id"]: b for b in merged}
    assert by_id["keep-me"]["sql_script"] == "SELECT old"
    assert by_id["change-me"]["sql_script"] == "SELECT new2"
    assert "stray" not in by_id
