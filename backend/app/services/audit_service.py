"""Audit service — thin orchestration over the append-only audit repo (NFR-7)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.domain.enums import AuditAction
from app.repositories.audit_repo import AuditRepo


class AuditService:
    def __init__(self, db: Session):
        self.repo = AuditRepo(db)
        self.db = db

    def log(
        self,
        *,
        user_id: str,
        action: AuditAction,
        target_type: str | None = None,
        target_id: str | None = None,
        detail: dict | None = None,
    ) -> None:
        self.repo.record(
            user_id=user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            detail=detail,
        )
        self.db.commit()
