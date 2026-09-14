"""Add-scenario ADDITIONAL_RESULT_BLOCKS retry and NONE filtering."""
from unittest.mock import MagicMock, patch

from app.services.ai_services.datamart.pipeline_retry import RepairBudget
from app.services.ai_services.datamart.scenario.scenario_pipeline import (
    add_scenario_specs_need_retry,
    filter_executable_add_scenario_specs,
    recover_add_scenario_specs_with_retry,
    validate_add_scenario_specs_against_grounding,
)
from app.services.ai_services.datamart.schema_broker import SchemaGrounding


def test_filter_executable_drops_none_sql() -> None:
    specs = [
        {"block_id": "aaaa-bbbb-cccc-dddd", "title": "t", "sql": "NONE"},
        {
            "block_id": "bbbb-cccc-dddd-eeee",
            "title": "ok",
            "sql": "SELECT 1 AS x LIMIT 10",
        },
    ]
    out = filter_executable_add_scenario_specs(specs)
    assert len(out) == 1
    assert "SELECT" in out[0]["sql"]


def test_need_retry_when_blocks_had_none_only() -> None:
    llm = """
NARRATIVE:
Summary

ADDITIONAL_RESULT_BLOCKS:
```json
[{"block_id": "aaaa-bbbb-cccc-dddd", "title": "t", "sql": "NONE"}]
```
"""
    need, reason = add_scenario_specs_need_retry([], llm_output=llm)
    assert need is True
    assert "NONE" in reason


@patch("app.services.ai_services.datamart.scenario.scenario_pipeline.retry_add_scenario_llm")
def test_recover_with_retry_reparses_blocks(mock_retry: MagicMock) -> None:
    mock_retry.return_value = """
NARRATIVE:
Payroll by branch

ADDITIONAL_RESULT_BLOCKS:
```json
[{"block_id": "cccc-dddd-eeee-ffff", "title": "Payroll", "sql": "SELECT 1 AS x LIMIT 5"}]
```
"""
    grounding = SchemaGrounding(
        columns_by_table={"hr.vw_payroll_summary": ["employee_no", "basic_salary"]},
        source="test",
    )
    bad_llm = """
NARRATIVE:
No sql

ADDITIONAL_RESULT_BLOCKS:
```json
[{"block_id": "aaaa-bbbb-cccc-dddd", "title": "t", "sql": "NONE"}]
```
"""
    specs, narrative, used = recover_add_scenario_specs_with_retry(
        question="payroll summary by branch",
        narrative="No sql",
        llm_output=bad_llm,
        sql=None,
        post_process_config=None,
        grounding=grounding,
        history_text="(none)",
        system_prompt="sys",
        repair_budget=RepairBudget(max_attempts=1),
        trace=None,
    )
    assert mock_retry.called
    assert len(specs) == 1
    assert "SELECT" in specs[0]["sql"]
    assert "Payroll" in narrative or used


def test_validate_specs_fails_on_unknown_table() -> None:
    grounding = SchemaGrounding(
        columns_by_table={"hr.mart_employee_current": ["emp_fullname", "employee_no"]},
        source="test",
    )
    specs = [
        {
            "block_id": "aaaa-bbbb-cccc-dddd",
            "title": "Bad",
            "sql": "SELECT * FROM hr.dim_org_unit LIMIT 5",
        }
    ]
    _specs2, err = validate_add_scenario_specs_against_grounding(specs, grounding)
    assert err
