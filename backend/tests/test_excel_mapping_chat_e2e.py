"""End-to-end (real Postgres, real seeded `demo_tenant` catalogue) check that
ExcelMappingChatService.send_message actually works: creates a session,
builds a prompt grounded in the tenant's real field catalogue, and — the
core contract confirmed with the user — never lets the AI touch a header
outside the ones it was explicitly given to map."""

from __future__ import annotations

import pytest

from app.core.tenancy import TenantContext
from app.db.postgres import PostgresDatabase
from app.domain.enums import Role
from app.services.excel_mapping_ai.chat_service import ExcelMappingChatService
from app.services.excel_mapping_ai.runner import TurnResult

_SCHEMA = "demo_tenant"


@pytest.fixture()
def db_session():
    db = PostgresDatabase()
    session = db.session()
    session.info["pg_tenant_schema"] = _SCHEMA
    yield session
    session.rollback()
    session.close()
    db.dispose()


def _ctx() -> TenantContext:
    return TenantContext(
        tenant_id=_SCHEMA, pg_schema=_SCHEMA, acting_user_id="mapping-tester",
        role=Role.CLIENT_HR_ADMIN, on_behalf=False,
    )


class RecordingFakeRunner:
    def __init__(self, reply_mappings: list[dict] | None):
        self.reply_mappings = reply_mappings
        self.calls: list[str] = []

    async def run(self, *, prompt_text, settings):
        self.calls.append(prompt_text)
        return TurnResult(reply="Here's what I found.", mappings=self.reply_mappings)


@pytest.mark.asyncio
async def test_a_real_catalogue_ref_is_accepted_and_persisted(db_session):
    ctx = _ctx()
    runner = RecordingFakeRunner([{"header": "Emp No", "ref": "employee.emp_no"}])
    svc = ExcelMappingChatService(db_session, runner=runner)
    head = svc.create(ctx, title="Mapping check")

    result = await svc.send_message(
        ctx, head["id"], "What should 'Emp No' map to?",
        headers=["Emp No"], current_mapping={},
    )
    assert result["mappings"] == [{"header": "Emp No", "ref": "employee.emp_no"}]
    # The real catalogue reached the prompt (not a stub/empty reference).
    assert "employee.emp_no" in runner.calls[0]


@pytest.mark.asyncio
async def test_an_already_mapped_header_is_never_returned_even_if_the_ai_tries(db_session):
    ctx = _ctx()
    # The AI (mis)behaving: touching a header outside "headers to map".
    runner = RecordingFakeRunner([
        {"header": "Emp No", "ref": "employee.emp_no"},
        {"header": "Full Name", "ref": "employee.full_name"},  # not in headers=["Emp No"]
    ])
    svc = ExcelMappingChatService(db_session, runner=runner)
    head = svc.create(ctx, title="Mapping check 2")

    result = await svc.send_message(
        ctx, head["id"], "Map the rest",
        headers=["Emp No"], current_mapping={"Full Name": "employee.full_name"},
    )
    # Validation rejects the whole turn (one bad entry) and retries once with
    # the SAME (still bad) response — so it ends up with no accepted mapping,
    # never a silent partial acceptance of the out-of-scope header.
    assert result["mappings"] is None
    assert "Full Name" in result["reply"]
    assert len(runner.calls) == 2


@pytest.mark.asyncio
async def test_a_second_turn_folds_in_the_prior_transcript(db_session):
    ctx = _ctx()
    runner = RecordingFakeRunner(None)
    svc = ExcelMappingChatService(db_session, runner=runner)
    head = svc.create(ctx, title="Mapping check 3")

    await svc.send_message(ctx, head["id"], "What's 'W/H'?", headers=["W/H"], current_mapping={})
    await svc.send_message(ctx, head["id"], "It's withholding tax", headers=["W/H"], current_mapping={})

    second_prompt = runner.calls[1]
    assert "What's 'W/H'?" in second_prompt
    assert "It's withholding tax" in second_prompt
