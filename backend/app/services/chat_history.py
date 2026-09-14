"""ChatGPT-style chat history — persisted conversations with IMMUTABLE results.

A chat session stores its whole transcript (user/assistant messages AND the result
snapshot rendered for each report turn) in `ai_sessions.messages`. Re-opening a
session replays those stored messages verbatim — including the saved result rows —
so a past answer NEVER changes, even if the underlying datamart data has since
moved. (Running the report again is a separate, explicit action.)

Sessions are scoped to the tenant AND the user who created them.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.tenancy import TenantContext
from app.db.metadata import AISession


class ChatHistoryService:
    def __init__(self, db: Session):
        self.db = db

    def _owned(self, ctx: TenantContext, session_id: str) -> AISession | None:
        s = self.db.get(AISession, session_id)
        if s is None or s.created_by != ctx.acting_user_id:
            return None
        return s

    def find(self, ctx: TenantContext, session_id: str) -> AISession | None:
        """The raw ORM row (owned by ctx's user), for a caller that needs more
        than the plain dict shapes above — e.g. rule_report_ai's chat_service,
        which reads sample_sheet_headers/working_rule_spec directly."""
        return self._owned(ctx, session_id)

    @staticmethod
    def _head(s: AISession) -> dict:
        msgs = s.messages or []
        return {
            "id": s.id,
            "title": s.title or "New chat",
            "message_count": len(msgs),
            "updated_at": s.updated_at.isoformat() if s.updated_at else None,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }

    def create(self, ctx: TenantContext, title: str | None = None, kind: str = "data_spec") -> dict:
        s = AISession(
            created_by=ctx.acting_user_id,
            title=(title or "New chat")[:160], messages=[], kind=kind,
        )
        self.db.add(s)
        self.db.commit()
        return self._head(s)

    def list(self, ctx: TenantContext, limit: int = 100, kind: str = "data_spec") -> list[dict]:
        rows = self.db.scalars(
            select(AISession)
            .where(AISession.created_by == ctx.acting_user_id, AISession.kind == kind)
            .order_by(AISession.updated_at.desc())
            .limit(limit)
        ).all()
        return [self._head(r) for r in rows]

    def get(self, ctx: TenantContext, session_id: str) -> dict | None:
        s = self._owned(ctx, session_id)
        if s is None:
            return None
        return {
            **self._head(s),
            "messages": s.messages or [],
            "working_data_spec": s.working_data_spec,
            "working_rule_spec": s.working_rule_spec,
            "sample_sheet_filename": s.sample_sheet_filename,
            "source_sql_filename": s.source_sql_filename,
        }

    def get_for_template(self, ctx: TenantContext, session_id: str) -> dict | None:
        """Same shape as `get()`, but WITHOUT the `created_by` restriction —
        used only to resume a REPORT's linked chat conversation (which any
        user in the tenant editing that report should be able to see and
        continue, not just whoever originally built it). Still safely
        tenant-isolated: `self.db` is already bound to ctx's schema at the
        connection level (schema-per-tenant), so this only ever widens
        access to "anyone in this tenant," never across tenants. Deliberately
        a separate method from `get()` so the general per-user "my chats"
        list elsewhere is never accidentally loosened."""
        s = self.db.get(AISession, session_id)
        if s is None:
            return None
        return {
            **self._head(s),
            "messages": s.messages or [],
            "working_data_spec": s.working_data_spec,
            "working_rule_spec": s.working_rule_spec,
            "sample_sheet_filename": s.sample_sheet_filename,
            "source_sql_filename": s.source_sql_filename,
        }

    def append(
        self, ctx: TenantContext, session_id: str, messages: list[dict],
        working_data_spec: dict | None = None,
        working_rule_spec: dict | None = None,
    ) -> dict | None:
        """Append a turn's messages (incl. any result snapshot) to the transcript.
        Reassigns the list so SQLAlchemy persists the JSONB change. Sets the title
        from the first user message if the session is still untitled."""
        s = self._owned(ctx, session_id)
        if s is None:
            return None
        existing = list(s.messages or [])
        if (not s.title or s.title == "New chat"):
            first_user = next((m.get("text") for m in messages if m.get("role") == "you" and m.get("text")), None)
            if first_user:
                s.title = first_user[:160]
        s.messages = existing + list(messages)
        if working_data_spec is not None:
            s.working_data_spec = working_data_spec
        if working_rule_spec is not None:
            s.working_rule_spec = working_rule_spec
        self.db.commit()
        return self._head(s)

    def rename(self, ctx: TenantContext, session_id: str, title: str) -> dict | None:
        s = self._owned(ctx, session_id)
        if s is None:
            return None
        s.title = (title or "Untitled").strip()[:160]
        self.db.commit()
        return self._head(s)

    def delete(self, ctx: TenantContext, session_id: str) -> bool:
        s = self._owned(ctx, session_id)
        if s is None:
            return False
        self.db.delete(s)
        self.db.commit()
        return True
