"""Metadata-DB access for the versioned semantic layer."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.metadata import SemanticModel
from app.domain.semantic import SemanticCatalog


class SemanticRepo:
    def __init__(self, db: Session):
        self.db = db

    def latest_version(self) -> int | None:
        row = self.db.execute(
            select(SemanticModel.version)
            .order_by(SemanticModel.version.desc())
            .limit(1)
        ).scalar_one_or_none()
        return row

    def get(self, version: int) -> SemanticCatalog | None:
        row = self.db.execute(
            select(SemanticModel).where(SemanticModel.version == version)
        ).scalar_one_or_none()
        if row is None:
            return None
        return SemanticCatalog.model_validate(row.catalog)

    def save_new_version(self, catalog: SemanticCatalog) -> SemanticModel:
        model = SemanticModel(
            version=catalog.version,
            catalog=catalog.model_dump(mode="json"),
        )
        self.db.add(model)
        self.db.flush()
        return model
