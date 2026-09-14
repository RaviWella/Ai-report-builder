"""Verify modify / scenario modes use the same recovery loop as new questions."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.ai_services.datamart.models import FollowUpMode
from app.services.ai_services.datamart.pipeline.runner import run_chat_pipeline
from app.services.ai_services.datamart.schema_broker import SchemaGrounding
from app.services.ai_services.datamart.prompts.simple_context import SimpleChatContext


def _mock_context() -> SimpleChatContext:
    grounding = SchemaGrounding(
        columns_by_table={
            "hr.mart_employee_current": [
                "emp_no",
                "emp_fullname",
                "emp_status",
                "designation_department",
            ],
            "hr_semantic.vw_pending_leave_approvals": [
                "leave_type",
                "approval_status",
                "leave_apply_date",
            ],
        },
        source="test",
    )
    return SimpleChatContext(
        mappings_text="(mappings)",
        datahub_text="(datahub)",
        schema_text="(schema)",
        grounding=grounding,
        table_short_names=["mart_employee_current", "vw_pending_leave_approvals"],
    )


def _llm_response(sql: str, narrative: str = "Done.") -> str:
    return f"NARRATIVE:\n{narrative}\n\nSQL:\n```sql\n{sql}\n```"


ANCHOR_SQL = """
SELECT e.emp_no, e.emp_fullname, e.designation_department
FROM hr.mart_employee_current e
WHERE COALESCE(e.emp_status, '') ILIKE '%active%'
LIMIT 500
"""


@patch("app.services.ai_services.datamart.pipeline.runner.execute_sql")
@patch("app.services.ai_services.datamart.pipeline.runner.call_llm")
@patch("app.services.ai_services.datamart.pipeline.runner.build_simple_chat_context")
def test_modify_mode_retries_after_execute_error(
    mock_build_ctx: MagicMock,
    mock_llm: MagicMock,
    mock_exec: MagicMock,
) -> None:
    mock_build_ctx.return_value = _mock_context()
    bad_sql = ANCHOR_SQL.replace("emp_no", "emp_number")
    good_sql = ANCHOR_SQL.replace("LIMIT 500", "LIMIT 100")
    mock_llm.side_effect = [
        _llm_response(bad_sql),
        _llm_response(good_sql),
    ]
    mock_exec.side_effect = [
        RuntimeError('column e.emp_number does not exist'),
        (["emp_no", "emp_fullname"], [["1", "Ann"]], 1),
    ]

    resp = run_chat_pipeline(
        question="limit to 100 rows",
        history_text="User: headcount\nAssistant: here",
        follow_up_mode=FollowUpMode.CONTINUE_LAST,
        previous_primary_sql=ANCHOR_SQL,
    )

    assert mock_llm.call_count == 2
    assert resp.row_count == 1
    assert resp.error is None
    assert resp.pipeline_trace is not None
    assert resp.pipeline_trace.recovery_events
    retry_prompt = mock_llm.call_args_list[1][0][1]
    assert "Modify mode" in retry_prompt or "Anchored SQL" in retry_prompt
    assert "emp_number" in retry_prompt or "does not exist" in retry_prompt


@patch("app.services.ai_services.datamart.pipeline.runner.execute_sql")
@patch("app.services.ai_services.datamart.pipeline.runner.call_llm")
@patch("app.services.ai_services.datamart.pipeline.runner.build_simple_chat_context")
def test_modify_mode_retries_when_sql_ignores_anchor(
    mock_build_ctx: MagicMock,
    mock_llm: MagicMock,
    mock_exec: MagicMock,
) -> None:
    mock_build_ctx.return_value = _mock_context()
    unrelated = "SELECT p.amount FROM hr.vw_payroll_summary p LIMIT 500"
    anchored = ANCHOR_SQL.replace("LIMIT 500", "LIMIT 200")
    mock_llm.side_effect = [
        _llm_response(unrelated),
        _llm_response(anchored),
    ]
    mock_exec.return_value = (["emp_no"], [["1"]], 1)

    resp = run_chat_pipeline(
        question="show only 200 rows",
        history_text="User: employees\nAssistant: list",
        follow_up_mode=FollowUpMode.CONTINUE_LAST,
        previous_primary_sql=ANCHOR_SQL,
    )

    assert mock_llm.call_count == 2
    assert resp.row_count == 1
    retry_prompt = mock_llm.call_args_list[1][0][1]
    assert "Modify mode" in retry_prompt or "anchored" in retry_prompt.lower()


@patch("app.services.ai_services.datamart.pipeline.runner.execute_sql")
@patch("app.services.ai_services.datamart.pipeline.runner.call_llm")
@patch("app.services.ai_services.datamart.pipeline.runner.build_simple_chat_context")
def test_scenario_mode_passes_add_scenario_instructions_on_retry(
    mock_build_ctx: MagicMock,
    mock_llm: MagicMock,
    mock_exec: MagicMock,
) -> None:
    mock_build_ctx.return_value = _mock_context()
    bad = "SELECT leave_type FROM hr_semantic.vw_pending_leave_approvals WHERE approval_status = 'Pending' LIMIT 500"
    good = "SELECT leave_type FROM hr_semantic.vw_pending_leave_approvals LIMIT 500"
    mock_llm.side_effect = [
        _llm_response(bad),
        _llm_response(good),
    ]
    mock_exec.side_effect = [
        ([], [], 0),
        (["leave_type"], [["Annual"]], 1),
    ]

    with patch(
        "app.services.ai_services.datamart.semantic.column_value_peek.peek_distinct_values",
        return_value=["pending"],
    ):
        resp = run_chat_pipeline(
            question="Add pending leave types as a second scenario",
            history_text="User: headcount\nAssistant: done\n```sql\nSELECT 1```",
            follow_up_mode=FollowUpMode.ADD_SCENARIO,
            previous_primary_sql=ANCHOR_SQL,
        )

    assert mock_llm.call_count >= 2
    assert resp.row_count == 1
    first_prompt = mock_llm.call_args_list[0][0][1]
    retry_prompt = mock_llm.call_args_list[1][0][1]
    assert "Add scenario" in first_prompt
    assert "Add scenario" in retry_prompt or "scenario" in retry_prompt.lower()
    assert "SELECT 1" not in first_prompt
    assert "headcount" in first_prompt


@patch("app.services.ai_services.datamart.pipeline.runner.execute_sql")
@patch("app.services.ai_services.datamart.pipeline.runner.call_llm")
@patch("app.services.ai_services.datamart.pipeline.runner.build_simple_chat_context")
def test_scenario_mode_deterministic_join_repair_before_llm_retry(
    mock_build_ctx: MagicMock,
    mock_llm: MagicMock,
    mock_exec: MagicMock,
) -> None:
    mock_build_ctx.return_value = _mock_context()
    bad_join = """
SELECT fl.leave_type, m.emp_fullname
FROM hr.fact_leave_transaction fl
JOIN hr.mart_employee_current m ON m.employee_sk = fl.source_approved_by
LIMIT 500
"""
    mock_llm.return_value = _llm_response(bad_join)
    mock_exec.side_effect = [
        RuntimeError("operator does not exist: text = integer"),
        (["leave_type", "emp_fullname"], [["Annual", "Bob"]], 1),
    ]

    resp = run_chat_pipeline(
        question="Add leave approver names",
        history_text="User: report\nAssistant: ok",
        follow_up_mode=FollowUpMode.ADD_SCENARIO,
        previous_primary_sql=ANCHOR_SQL,
    )

    assert resp.row_count == 1
    assert resp.error is None
    assert mock_llm.call_count == 1
    assert mock_exec.call_count == 2
