"""Per-tenant reusable pool of manual fields (Document Studio).

A manual field is a value the issuer types at generation time (e.g. 'Effective
Date' -> {{manual.effective_date}}). Pooled at the tenant level so any letter can
reuse the same set instead of re-creating fields per letter. Strictly tenant-scoped
— one tenant's pool is never visible to another.
"""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.tenancy import TenantContext
from app.db.metadata import ManualField


def slugify_key(label: str) -> str:
    """Label -> token key: lower snake_case, [a-z0-9_] only (matches {{manual.key}})."""
    key = re.sub(r"[^a-z0-9]+", "_", (label or "").strip().lower()).strip("_")
    return key


class ManualFieldService:
    def __init__(self, db: Session):
        self.db = db

    def list(self, ctx: TenantContext) -> list[dict]:
        rows = self.db.execute(
            select(ManualField).order_by(ManualField.label)
        ).scalars().all()
        return [{"id": r.id, "key": r.key, "label": r.label} for r in rows]

    def create(self, ctx: TenantContext, label: str, key: str | None = None) -> dict:
        label = (label or "").strip()
        if not label:
            raise ValueError("A field label is required.")
        key = slugify_key(key or label)
        if not key:
            raise ValueError("Couldn’t derive a field key from that label.")
        # Idempotent: reuse an existing pool entry with the same key for this tenant.
        existing = self.db.execute(
            select(ManualField).where(
                ManualField.key == key,
            )
        ).scalar_one_or_none()
        if existing:
            return {"id": existing.id, "key": existing.key, "label": existing.label}
        row = ManualField(
            key=key, label=label,
            created_by=ctx.acting_user_id,
        )
        self.db.add(row)
        self.db.commit()
        return {"id": row.id, "key": row.key, "label": row.label}

    def delete(self, ctx: TenantContext, field_id: str) -> None:
        row = self.db.get(ManualField, field_id)
        if row is not None:
            self.db.delete(row)
            self.db.commit()
