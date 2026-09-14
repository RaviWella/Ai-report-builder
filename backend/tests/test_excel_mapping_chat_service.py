"""The validate-then-retry-once loop for the Excel-mapping chat, tested
against a FAKE runner — no live Claude Code call, no database. Mirrors
test_rule_report_ai_chat_service.py's approach for _run_and_validate, the
one piece of chat_service.py that doesn't touch self.db."""

from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.domain.enums import FieldRole, FieldType
from app.domain.semantic import Entity, PhysicalColumn, SemanticCatalog, SemanticField
from app.services.excel_mapping_ai.chat_service import ExcelMappingChatService
from app.services.excel_mapping_ai.runner import TurnResult


def _catalog() -> SemanticCatalog:
    field = SemanticField(
        ref="employee.emp_no", label="Employee No", type=FieldType.STRING, role=FieldRole.DIMENSION,
        physical=PhysicalColumn(table="dim_employee", column="emp_no"),
    )
    entity = Entity(
        name="Employee", key="employee", base_schema="mart", base_table="dim_employee",
        primary_key="employee_sk", fields=[field],
    )
    return SemanticCatalog(tenant_id="t", version=1, entities=[entity])


class FakeRunner:
    def __init__(self, turns: list[TurnResult]):
        self.turns = list(turns)
        self.calls: list[str] = []

    async def run(self, *, prompt_text, settings):
        self.calls.append(prompt_text)
        return self.turns.pop(0)


def _service(runner: FakeRunner) -> ExcelMappingChatService:
    return ExcelMappingChatService(db=None, runner=runner)


@pytest.mark.asyncio
async def test_no_mappings_yet_returns_the_ai_reply_with_no_retry():
    runner = FakeRunner([TurnResult(reply="What does 'W/H' stand for?", mappings=None)])
    turn = await _service(runner)._run_and_validate("hi", _catalog(), ["W/H"], get_settings())
    assert turn.mappings is None
    assert turn.reply == "What does 'W/H' stand for?"
    assert len(runner.calls) == 1


@pytest.mark.asyncio
async def test_a_valid_mapping_on_the_first_try_needs_no_retry():
    runner = FakeRunner([TurnResult(reply="Mapped it.", mappings=[{"header": "Emp No", "ref": "employee.emp_no"}])])
    turn = await _service(runner)._run_and_validate("hi", _catalog(), ["Emp No"], get_settings())
    assert turn.mappings == [{"header": "Emp No", "ref": "employee.emp_no"}]
    assert len(runner.calls) == 1


@pytest.mark.asyncio
async def test_an_invalid_ref_is_retried_once_with_the_exact_error():
    runner = FakeRunner([
        TurnResult(reply="Mapped it.", mappings=[{"header": "Emp No", "ref": "made_up.ref"}]),
        TurnResult(reply="Fixed it.", mappings=[{"header": "Emp No", "ref": "employee.emp_no"}]),
    ])
    turn = await _service(runner)._run_and_validate("hi", _catalog(), ["Emp No"], get_settings())
    assert turn.mappings == [{"header": "Emp No", "ref": "employee.emp_no"}]
    assert turn.reply == "Fixed it."
    assert len(runner.calls) == 2
    assert "made_up.ref" in runner.calls[1]


@pytest.mark.asyncio
async def test_a_header_outside_the_allowed_list_is_retried_and_then_dropped_if_still_bad():
    runner = FakeRunner([
        TurnResult(reply="Mapped it.", mappings=[{"header": "Already Mapped Header", "ref": "employee.emp_no"}]),
        TurnResult(reply="Still wrong.", mappings=[{"header": "Already Mapped Header", "ref": "employee.emp_no"}]),
    ])
    turn = await _service(runner)._run_and_validate("hi", _catalog(), ["Emp No"], get_settings())
    assert turn.mappings is None
    assert "Already Mapped Header" in turn.reply
    assert len(runner.calls) == 2


@pytest.mark.asyncio
async def test_ai_asking_a_clarifying_question_on_retry_drops_the_stale_error():
    runner = FakeRunner([
        TurnResult(reply="Mapped it.", mappings=[{"header": "Emp No", "ref": "made_up.ref"}]),
        TurnResult(reply="Actually — is this the employee code or the payroll code?", mappings=None),
    ])
    turn = await _service(runner)._run_and_validate("hi", _catalog(), ["Emp No"], get_settings())
    assert turn.mappings is None
    assert turn.reply == "Actually — is this the employee code or the payroll code?"
    assert "made_up.ref" not in turn.reply
