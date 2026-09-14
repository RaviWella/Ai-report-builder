"""Per-tenant letterhead presets (logo + header + footer) for the Document Studio."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.tenancy import TenantContext
from app.db.metadata import Letterhead


def _dump(row: Letterhead) -> dict:
    return {
        "id": row.id, "name": row.name,
        "logo_data_url": row.logo_data_url,
        "header_html": row.header_html or "",
        "footer_html": row.footer_html or "",
    }


class LetterheadService:
    def __init__(self, db: Session):
        self.db = db

    def list(self, ctx: TenantContext) -> list[dict]:
        rows = self.db.execute(
            select(Letterhead).order_by(Letterhead.name)
        ).scalars().all()
        return [_dump(r) for r in rows]

    def create(self, ctx: TenantContext, *, name: str, logo_data_url: str | None,
               header_html: str | None, footer_html: str | None) -> dict:
        name = (name or "").strip()
        if not name:
            raise ValueError("A letterhead name is required.")
        row = Letterhead(
            name=name, logo_data_url=logo_data_url,
            header_html=header_html, footer_html=footer_html, created_by=ctx.acting_user_id,
        )
        self.db.add(row)
        self.db.commit()
        return _dump(row)

    def update(self, ctx: TenantContext, letterhead_id: str, *, name: str | None,
               logo_data_url: str | None, header_html: str | None, footer_html: str | None) -> dict:
        row = self.db.get(Letterhead, letterhead_id)
        if row is None:
            raise ValueError("Letterhead not found.")
        if name is not None and name.strip():
            row.name = name.strip()
        if logo_data_url is not None:
            row.logo_data_url = logo_data_url or None
        if header_html is not None:
            row.header_html = header_html
        if footer_html is not None:
            row.footer_html = footer_html
        self.db.commit()
        return _dump(row)

    def delete(self, ctx: TenantContext, letterhead_id: str) -> None:
        row = self.db.get(Letterhead, letterhead_id)
        if row is not None:
            self.db.delete(row)
            self.db.commit()
