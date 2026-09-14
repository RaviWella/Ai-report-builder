"""Append-only audit log access (NFR-7)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.metadata import AuditLog
from app.domain.enums import AuditAction


class AuditRepo:
    def __init__(self, db: Session):
        self.db = db

    def record(
        self,
        *,
        user_id: str,
        action: AuditAction,
        target_type: str | None = None,
        target_id: str | None = None,
        detail: dict | None = None,
    ) -> AuditLog:
        entry = AuditLog(
            user_id=user_id,
            action=action.value,
            target_type=target_type,
            target_id=target_id,
            detail=detail or {},
        )
        self.db.add(entry)
        self.db.flush()
        return entry

    def list_recent(self, limit: int = 200) -> list[AuditLog]:
        return list(
            self.db.execute(
                select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
            ).scalars()
        )
