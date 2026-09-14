"""Field-request (data-capture gap) store — the honest path for a column whose
data simply isn't in the datamart yet.

When a user uploads a sheet with a heading that has NO field in the catalogue
(e.g. "Actual In Time" before attendance punches are exposed), we don't fake a
mapping — we log the request here, per tenant. It then surfaces on the Data Health
dashboard so the ETL team can expose the field. De-duplicated per (tenant,
header_key): a repeat request bumps `hits` and refreshes the timestamp.
"""

from __future__ import annotations

import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.metadata import FieldRequest

log = get_logger(__name__)

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


class FieldRequestStore:
    """Per-tenant data-capture gap list over the `field_request` table."""

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def header_key(header: str) -> str:
        return _NON_ALNUM.sub(" ", header.lower()).strip()

    def request(self, tenant_id: str, header: str, note: str | None, *, user_id: str) -> dict | None:
        """Log (or bump) a request for a not-yet-available field. Reopens a resolved
        request if asked again. Returns the row, or None for a blank header."""
        key = self.header_key(header)
        if not key:
            return None
        row = self.db.scalar(
            select(FieldRequest).where(
                FieldRequest.header_key == key
            )
        )
        if row is None:
            row = FieldRequest(
                header_key=key, header_sample=header[:255],
                note=(note or None), requested_by=user_id,
            )
            self.db.add(row)
        else:
            row.hits += 1
            row.last_requested_at = func.now()
            row.header_sample = header[:255]
            if note:
                row.note = note
            if row.status == "resolved":  # asked again — reopen
                row.status, row.resolved_at = "open", None
        self.db.commit()
        self.db.refresh(row)
        return self._to_dict(row)

    def list(self, tenant_id: str, limit: int = 500) -> list[dict]:
        """All requests for a tenant — open first, then most-requested."""
        rows = self.db.scalars(
            select(FieldRequest)
            
            .order_by(
                (FieldRequest.status == "open").desc(),
                FieldRequest.hits.desc(),
                FieldRequest.last_requested_at.desc(),
            )
            .limit(limit)
        ).all()
        return [self._to_dict(r) for r in rows]

    def set_status(self, tenant_id: str, request_id: str, status: str) -> dict | None:
        row = self.db.scalar(
            select(FieldRequest).where(
                FieldRequest.id == request_id
            )
        )
        if row is None:
            return None
        row.status = "resolved" if status == "resolved" else "open"
        row.resolved_at = func.now() if row.status == "resolved" else None
        self.db.commit()
        self.db.refresh(row)
        return self._to_dict(row)

    def delete_by_id(self, tenant_id: str, request_id: str) -> bool:
        row = self.db.scalar(
            select(FieldRequest).where(
                FieldRequest.id == request_id
            )
        )
        if row is None:
            return False
        self.db.delete(row)
        self.db.commit()
        return True

    @staticmethod
    def _to_dict(r: FieldRequest) -> dict:
        return {
            "id": r.id, "header": r.header_sample, "note": r.note,
            "status": r.status, "hits": r.hits,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "last_requested_at": r.last_requested_at.isoformat() if r.last_requested_at else None,
            "resolved_at": r.resolved_at.isoformat() if r.resolved_at else None,
        }
