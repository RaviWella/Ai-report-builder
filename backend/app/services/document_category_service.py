"""Per-tenant, per-type document categories (Document Studio).

Free-form and fully dynamic: a tenant creates/renames/deletes their own categories
under each document type. Templates reference a category by NAME (mirrored to
ReportTemplate.module), so renaming a category here is cosmetic for the list — it
does not need to rewrite templates, which keep their stored category string.
"""

from __future__ import annotations

from sqlalchemy import select

from sqlalchemy.orm import Session

from app.core.tenancy import TenantContext
from app.db.metadata import DocumentCategory
from app.services.document_service import DOC_TYPES


class DocumentCategoryService:
    def __init__(self, db: Session):
        self.db = db

    def list(self, ctx: TenantContext, doc_type: str) -> list[dict]:
        rows = self.db.execute(
            select(DocumentCategory)
            .where(
                DocumentCategory.doc_type == doc_type,
            )
            .order_by(DocumentCategory.name)
        ).scalars().all()
        return [{"id": r.id, "name": r.name, "doc_type": r.doc_type} for r in rows]

    def create(self, ctx: TenantContext, doc_type: str, name: str) -> dict:
        if doc_type not in DOC_TYPES:
            raise ValueError(f"Unknown document type {doc_type!r}")
        name = (name or "").strip()
        if not name:
            raise ValueError("Category name is required.")
        existing = self.db.execute(
            select(DocumentCategory).where(
                DocumentCategory.doc_type == doc_type,
                DocumentCategory.name == name,
            )
        ).scalar_one_or_none()
        if existing:
            return {"id": existing.id, "name": existing.name, "doc_type": existing.doc_type}
        row = DocumentCategory(
            doc_type=doc_type, name=name,
            created_by=ctx.acting_user_id,
        )
        self.db.add(row)
        self.db.commit()
        return {"id": row.id, "name": row.name, "doc_type": row.doc_type}

    def rename(self, ctx: TenantContext, category_id: str, name: str) -> dict:
        row = self.db.get(DocumentCategory, category_id)
        if row is None:
            raise ValueError("Category not found.")
        name = (name or "").strip()
        if not name:
            raise ValueError("Category name is required.")
        row.name = name
        self.db.commit()
        return {"id": row.id, "name": row.name, "doc_type": row.doc_type}

    def delete(self, ctx: TenantContext, category_id: str) -> None:
        row = self.db.get(DocumentCategory, category_id)
        if row is not None:
            self.db.delete(row)
            self.db.commit()
