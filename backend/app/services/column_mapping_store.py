"""Learned column-mapping store — "map a header once, remember it forever".

The Excel upload flow guesses a semantic field for each spreadsheet header
(fuzzy-match first, AI for leftovers). Unusual headers — "Punch In Location",
"Preferred Name" — can mis-map. When a user confirms or corrects a mapping in
the review UI, we remember the NORMALISED header → ref here, per tenant. The next
upload of a sheet with the same heading is auto-corrected from memory, so the fix
is made once and never again — the same production consistency guarantee the NL
learning store gives, applied to column mapping.

`ref` NULL means the user deliberately skipped that header (a remembered skip).
The header key is normalised (lower-cased, punctuation folded to spaces, order
preserved) so "EMP No", "emp  no." and "Emp No" collapse to one entry, while
order-meaningful pairs like "Punch In" vs "Punch Out" stay distinct.
"""

from __future__ import annotations

import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.metadata import LearnedColumnMapping

log = get_logger(__name__)

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


class ColumnMappingStore:
    """Per-tenant header → field memory over the `learned_column_mapping` table."""

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def header_key(header: str) -> str:
        """Stable lookup key for a spreadsheet header: lower-cased, punctuation and
        whitespace collapsed to single spaces, order preserved."""
        return _NON_ALNUM.sub(" ", header.lower()).strip()

    def lookup_all(self, tenant_id: str) -> dict[str, str | None]:
        """All remembered mappings for a tenant as {header_key: ref_or_None}. The
        presence of a key means "learned" (value None = a remembered skip)."""
        rows = self.db.scalars(
            select(LearnedColumnMapping).where(True)
        ).all()
        return {r.header_key: r.ref for r in rows}

    def bump(self, tenant_id: str, header_keys: list[str]) -> None:
        """Record that these learned mappings were applied (usage counter). Best-
        effort — never raises into the mapping path."""
        if not header_keys:
            return
        try:
            self.db.query(LearnedColumnMapping).filter(
                LearnedColumnMapping.header_key.in_(header_keys),
            ).update(
                {"hits": LearnedColumnMapping.hits + 1, "last_used_at": func.now()},
                synchronize_session=False,
            )
            self.db.commit()
        except Exception as exc:  # noqa: BLE001 - usage tracking must never break mapping
            self.db.rollback()
            log.warning("colmap_bump_failed", error=str(exc)[:160])

    def remember(self, tenant_id: str, header: str, ref: str | None, *, user_id: str) -> None:
        """Learn a (header → ref) mapping. `ref=None` remembers a skip. Idempotent
        per (tenant, header_key): the latest choice wins. Best-effort."""
        key = self.header_key(header)
        if not key:
            return
        try:
            row = self.db.scalar(
                select(LearnedColumnMapping).where(
                    LearnedColumnMapping.header_key == key,
                )
            )
            if row is None:
                self.db.add(
                    LearnedColumnMapping(
                        header_key=key, header_sample=header[:255],
                        ref=ref, created_by=user_id,
                    )
                )
            else:
                row.ref, row.header_sample, row.last_used_at = ref, header[:255], func.now()
            self.db.commit()
        except Exception as exc:  # noqa: BLE001 - learning must never break the upload
            self.db.rollback()
            log.warning("colmap_remember_failed", error=str(exc)[:160])

    def list(self, tenant_id: str, limit: int = 500) -> list[dict]:
        """Remembered mappings for a tenant — most-used first (governance view)."""
        rows = self.db.scalars(
            select(LearnedColumnMapping)
            .where(True)
            .order_by(LearnedColumnMapping.hits.desc(), LearnedColumnMapping.last_used_at.desc())
            .limit(limit)
        ).all()
        return [
            {
                "id": r.id, "header": r.header_sample, "header_key": r.header_key,
                "ref": r.ref, "hits": r.hits,
                "last_used_at": r.last_used_at.isoformat() if r.last_used_at else None,
            }
            for r in rows
        ]

    def delete_by_id(self, tenant_id: str, mapping_id: str) -> bool:
        """Forget a remembered mapping (e.g. one an admin no longer wants applied)."""
        row = self.db.scalar(
            select(LearnedColumnMapping).where(
                LearnedColumnMapping.id == mapping_id,
            )
        )
        if row is None:
            return False
        self.db.delete(row)
        self.db.commit()
        return True
