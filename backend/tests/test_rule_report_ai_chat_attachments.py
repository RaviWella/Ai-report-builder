"""Nobody had ever mechanically verified that the 3 chat attachments
(requirement doc / sample sheet / source SQL) actually reach the AI — only
eyeballed the code path (client.ts -> rule_chat.py -> chat_service.py ->
runner.py). This closes that gap with a real Postgres session + a FakeRunner
that records exactly what chat_service.py hands it, per turn.
"""

from __future__ import annotations

import pytest

from app.core.tenancy import TenantContext
from app.db.postgres import PostgresDatabase
from app.domain.enums import Role
from app.services.rule_report_ai.chat_service import RuleReportChatService
from app.services.rule_report_ai.runner import TurnResult

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
        tenant_id=_SCHEMA, pg_schema=_SCHEMA, acting_user_id="attach-tester",
        role=Role.CLIENT_HR_ADMIN, on_behalf=False,
    )


class RecordingFakeRunner:
    """Same shape as chat_service.py's expected runner, but records every
    call's prompt_text/attachment_blocks instead of touching a live Claude
    Code process — so we can assert on exactly what reached "the AI"."""

    def __init__(self):
        self.calls: list[dict] = []

    async def run(self, *, prompt_text, attachment_blocks, settings, ctx=None, session_id=""):
        self.calls.append({"prompt_text": prompt_text, "attachment_blocks": attachment_blocks})
        return TurnResult(reply="Got it.", spec=None)


_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0"
    b"\x00\x00\x03\x01\x01\x00\x18\xdd\x8d\xb0\x00\x00\x00\x00IEND\xaeB`\x82"
)
_SAMPLE_CSV = b"employee_no,total_hours\nEMP001,42.5\nEMP002,38.0\n"
_SOURCE_SQL = "SELECT emp_id, SUM(hrs) AS total_hrs FROM legacy_timesheet GROUP BY emp_id"


@pytest.mark.asyncio
async def test_requirement_doc_reaches_the_ai_and_persists_across_turns(db_session):
    ctx = _ctx()
    runner = RecordingFakeRunner()
    svc = RuleReportChatService(db_session, runner=runner)
    head = svc.create(ctx, title="Attachment check")

    await svc.send_message(
        ctx, head["id"], "Here's the client's requirement screenshot",
        requirement_doc=(_PNG_BYTES, "requirement.png", "image/png"),
    )
    first_blocks = runner.calls[0]["attachment_blocks"]
    assert any(b.get("type") == "image" for b in first_blocks)

    # A SECOND turn, with no new attachment at all — the doc must still be
    # re-attached, since it's part of the report's requirement, not a one-off.
    await svc.send_message(ctx, head["id"], "Also only include active employees")
    second_blocks = runner.calls[1]["attachment_blocks"]
    assert any(b.get("type") == "image" for b in second_blocks)


@pytest.mark.asyncio
async def test_sample_sheet_headers_reach_the_ai_prompt(db_session):
    ctx = _ctx()
    runner = RecordingFakeRunner()
    svc = RuleReportChatService(db_session, runner=runner)
    head = svc.create(ctx, title="Sample sheet check")

    await svc.send_message(
        ctx, head["id"], "Match this output shape",
        sample_sheet=(_SAMPLE_CSV, "sample.csv", "text/csv"),
    )
    prompt = runner.calls[0]["prompt_text"]
    assert "employee_no" in prompt
    assert "total_hours" in prompt


@pytest.mark.asyncio
async def test_source_sql_reaches_the_ai_prompt(db_session):
    ctx = _ctx()
    runner = RecordingFakeRunner()
    svc = RuleReportChatService(db_session, runner=runner)
    head = svc.create(ctx, title="Source SQL check")

    await svc.send_message(
        ctx, head["id"], "Rebuild this against the new datamart",
        source_sql=(_SOURCE_SQL.encode(), "legacy_query.sql", "text/plain"),
    )
    prompt = runner.calls[0]["prompt_text"]
    assert _SOURCE_SQL in prompt
