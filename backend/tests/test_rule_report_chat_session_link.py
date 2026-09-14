"""A rule report saved via the AI chat now records which chat session built
it (presentation_spec.chat_session_id) — so reopening the report to edit it
can resume that SAME conversation instead of starting blank. The lookup
(ReportService.rule_report_chat_session -> ChatHistoryService
.get_for_template) must be visible to ANY user in the tenant, not just
whoever created the session — real Postgres, real schema-per-tenant scoping,
confirming the created_by restriction genuinely doesn't apply here.
"""

from __future__ import annotations

import pytest

from app.core.tenancy import TenantContext
from app.db.postgres import PostgresDatabase
from app.domain.enums import Role
from app.services.chat_history import ChatHistoryService
from app.services.report_service import ReportService

_SCHEMA = "demo_tenant"
_MIN_SPEC = {
    "name": "chat_link_test_report",
    "source": "mart.mart_attendance_daily",
    "grain": ["employee_no"],
    "row_value": {"cases": [{"when": "worked_hours > 0", "value": "worked_hours"}], "else": "0"},
    "rollup": {"total": "sum(row_value)"},
    "output": ["employee_no", "total"],
}


@pytest.fixture()
def db_session():
    db = PostgresDatabase()
    session = db.session()
    session.info["pg_tenant_schema"] = _SCHEMA
    yield session
    session.rollback()
    session.close()
    db.dispose()


def _ctx(user: str) -> TenantContext:
    return TenantContext(
        tenant_id=_SCHEMA, pg_schema=_SCHEMA, acting_user_id=user,
        role=Role.CLIENT_HR_ADMIN, on_behalf=False,
    )


def test_saving_with_a_session_id_links_it_and_any_tenant_user_can_resume_it(db_session):
    author = _ctx("author-user")
    other = _ctx("a-different-builder")

    session_head = ChatHistoryService(db_session).create(author, title="Building the report")
    ChatHistoryService(db_session).append(
        author, session_head["id"],
        [{"role": "you", "text": "Build me a total-hours report"}],
    )

    created = ReportService(db_session).create_rule_report(
        author, name="Chat-linked report", spec=_MIN_SPEC, session_id=session_head["id"],
    )

    # The report's OWN publisher can resume it...
    resumed_by_author = ReportService(db_session).rule_report_chat_session(author, created["template_id"])
    assert resumed_by_author is not None
    assert resumed_by_author["id"] == session_head["id"]
    assert resumed_by_author["messages"][0]["text"] == "Build me a total-hours report"

    # ...and so can a DIFFERENT user in the same tenant (the tenant-wide
    # access requirement — ChatHistoryService.get() alone would return None
    # here, since it's scoped to created_by).
    resumed_by_other = ReportService(db_session).rule_report_chat_session(other, created["template_id"])
    assert resumed_by_other is not None
    assert resumed_by_other["id"] == session_head["id"]
    assert ChatHistoryService(db_session).get(other, session_head["id"]) is None  # confirms the contrast


def test_no_linked_session_returns_none_not_an_error(db_session):
    ctx = _ctx("solo-user")
    created = ReportService(db_session).create_rule_report(ctx, name="Plain report", spec=_MIN_SPEC)
    assert ReportService(db_session).rule_report_chat_session(ctx, created["template_id"]) is None


def test_a_deleted_or_missing_session_id_never_fails_the_save(db_session):
    ctx = _ctx("solo-user-2")
    created = ReportService(db_session).create_rule_report(
        ctx, name="Report with a bogus session", spec=_MIN_SPEC, session_id="does-not-exist",
    )
    assert created["template_id"]  # the save itself succeeded
    assert ReportService(db_session).rule_report_chat_session(ctx, created["template_id"]) is None
