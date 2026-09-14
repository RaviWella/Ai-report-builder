"""The validate-then-retry-once loop (never trust the AI's raw `spec`), tested
against a FAKE runner — no live Claude Code call, no database. This targets
RuleReportChatService._run_and_validate, the one piece of chat_service.py that
doesn't touch self.db, so it's cleanly unit-testable in isolation."""

import json
from pathlib import Path

import pytest

from app.core.config import get_settings
from app.core.tenancy import TenantContext
from app.domain.enums import Role
from app.services.rule_report_ai.chat_service import RuleReportChatService
from app.services.rule_report_ai.runner import TurnResult

_EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "app/services/rule_report_ai/examples"
_VALID_SPEC = json.loads((_EXAMPLES_DIR / "02_meal_plan_allowance_time_functions.json").read_text())
_CTX = TenantContext(tenant_id="t", pg_schema="t", acting_user_id="u", role=Role.CLIENT_HR_ADMIN, on_behalf=False)


def _invalid_spec() -> dict:
    bad = dict(_VALID_SPEC)
    bad["output"] = [*bad["output"], "not_a_real_column"]
    return bad


class FakeRunner:
    def __init__(self, turns: list[TurnResult]):
        self.turns = list(turns)
        self.calls: list[str] = []

    async def run(self, *, prompt_text, attachment_blocks, settings, ctx=None, session_id=""):
        self.calls.append(prompt_text)
        return self.turns.pop(0)


def _service(runner: FakeRunner) -> RuleReportChatService:
    return RuleReportChatService(db=None, runner=runner)


async def _run(service: RuleReportChatService, prompt_text: str, attachments: list):
    turn = await service._run_and_validate(
        prompt_text, attachments, get_settings(), ctx=_CTX, session_id="s1",
    )
    return turn.reply, turn.spec


@pytest.mark.asyncio
async def test_no_spec_yet_returns_the_ai_reply_with_no_retry():
    runner = FakeRunner([TurnResult(reply="What date range?", spec=None)])
    reply, spec = await _run(_service(runner), "hi", [])
    assert spec is None
    assert reply == "What date range?"
    assert len(runner.calls) == 1


@pytest.mark.asyncio
async def test_a_valid_spec_on_the_first_try_needs_no_retry():
    runner = FakeRunner([TurnResult(reply="Built it.", spec=_VALID_SPEC)])
    _, spec = await _run(_service(runner), "hi", [])
    assert spec is not None
    assert spec["name"] == "meal_plan_allowance"
    assert len(runner.calls) == 1


@pytest.mark.asyncio
async def test_an_invalid_spec_is_retried_once_with_the_exact_error():
    runner = FakeRunner([
        TurnResult(reply="Built it.", spec=_invalid_spec()),
        TurnResult(reply="Fixed it.", spec=_VALID_SPEC),
    ])
    reply, spec = await _run(_service(runner), "hi", [])
    assert spec is not None
    assert reply == "Fixed it."
    assert len(runner.calls) == 2
    assert "not_a_real_column" in runner.calls[1]


@pytest.mark.asyncio
async def test_a_spec_still_invalid_after_retry_surfaces_the_error_and_no_spec():
    runner = FakeRunner([
        TurnResult(reply="Built it.", spec=_invalid_spec()),
        TurnResult(reply="Still broken.", spec=_invalid_spec()),
    ])
    reply, spec = await _run(_service(runner), "hi", [])
    assert spec is None
    assert "not_a_real_column" in reply
    assert len(runner.calls) == 2


@pytest.mark.asyncio
async def test_ai_asking_a_clarifying_question_on_retry_drops_the_stale_error():
    runner = FakeRunner([
        TurnResult(reply="Built it.", spec=_invalid_spec()),
        TurnResult(reply="Actually — which shift types count?", spec=None),
    ])
    reply, spec = await _run(_service(runner), "hi", [])
    assert spec is None
    assert reply == "Actually — which shift types count?"
    assert "not_a_real_column" not in reply


_VALID_PIVOT = {"column_field": "work_date", "value_field": "hours", "status_field": "status"}


@pytest.mark.asyncio
async def test_a_valid_pivot_alongside_spec_passes_through_untouched():
    runner = FakeRunner([TurnResult(reply="Built it.", spec=_VALID_SPEC, pivot=_VALID_PIVOT)])
    turn = await _service(runner)._run_and_validate(
        "hi", [], get_settings(), ctx=_CTX, session_id="s1",
    )
    assert turn.spec is not None
    assert turn.pivot == _VALID_PIVOT
    assert len(runner.calls) == 1


@pytest.mark.asyncio
async def test_a_malformed_pivot_is_retried_once_with_the_exact_error():
    bad_pivot = {"value_field": "hours"}  # missing required column_field
    runner = FakeRunner([
        TurnResult(reply="Built it.", spec=_VALID_SPEC, pivot=bad_pivot),
        TurnResult(reply="Fixed it.", spec=_VALID_SPEC, pivot=_VALID_PIVOT),
    ])
    turn = await _service(runner)._run_and_validate(
        "hi", [], get_settings(), ctx=_CTX, session_id="s1",
    )
    assert turn.pivot == _VALID_PIVOT
    assert turn.reply == "Fixed it."
    assert len(runner.calls) == 2
    assert "column_field" in runner.calls[1]


@pytest.mark.asyncio
async def test_row_number_column_subtotal_totals_pass_through_unvalidated():
    # These three are simple presentation config (string/dict/list) — no
    # dedicated validator, just carried through from the (possibly retried) turn.
    runner = FakeRunner([TurnResult(
        reply="Built it.", spec=_VALID_SPEC,
        row_number_column="s_no", subtotal={"group_by": ["dept"]}, totals=["hours"],
    )])
    turn = await _service(runner)._run_and_validate(
        "hi", [], get_settings(), ctx=_CTX, session_id="s1",
    )
    assert turn.row_number_column == "s_no"
    assert turn.subtotal == {"group_by": ["dept"]}
    assert turn.totals == ["hours"]
