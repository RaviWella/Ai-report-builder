"""Metadata-DB access for report templates and their immutable versions."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.metadata import ReportTemplate, ReportTemplateVersion


class TemplateRepo:
    def __init__(self, db: Session):
        self.db = db

    def create_template(
        self, *, name: str, description: str | None, created_by: str,
        module: str = "General",
    ) -> ReportTemplate:
        tpl = ReportTemplate(
            name=name, description=description, created_by=created_by,
            module=module,
        )
        self.db.add(tpl)
        self.db.flush()
        return tpl

    def get_template(self, template_id: str) -> ReportTemplate | None:
        return self.db.execute(
            select(ReportTemplate).where(ReportTemplate.id == template_id)
        ).scalar_one_or_none()

    def list_templates(self) -> list[ReportTemplate]:
        return list(
            self.db.execute(
                select(ReportTemplate).order_by(ReportTemplate.created_at.desc())
            ).scalars()
        )

    def next_version_no(self, template_id: str) -> int:
        current = self.db.execute(
            select(ReportTemplateVersion.version_no)
            .where(ReportTemplateVersion.template_id == template_id)
            .order_by(ReportTemplateVersion.version_no.desc())
            .limit(1)
        ).scalar_one_or_none()
        return (current or 0) + 1

    def add_version(
        self,
        *,
        template_id: str,
        data_spec: dict,
        presentation_spec: dict,
        semantic_version_ref: int,
        status: str,
        created_by: str,
    ) -> ReportTemplateVersion:
        version = ReportTemplateVersion(
            template_id=template_id,
            version_no=self.next_version_no(template_id),
            data_spec=data_spec,
            presentation_spec=presentation_spec,
            semantic_version_ref=semantic_version_ref,
            status=status,
            created_by=created_by,
        )
        self.db.add(version)
        self.db.flush()
        return version

    def get_version(self, template_id: str, version_id: str) -> ReportTemplateVersion | None:
        return self.db.execute(
            select(ReportTemplateVersion).where(
                ReportTemplateVersion.id == version_id,
                ReportTemplateVersion.template_id == template_id,
            )
        ).scalar_one_or_none()

    def list_versions(self, template_id: str) -> list[ReportTemplateVersion]:
        return list(
            self.db.execute(
                select(ReportTemplateVersion)
                .where(ReportTemplateVersion.template_id == template_id)
                .order_by(ReportTemplateVersion.version_no.desc())
            ).scalars()
        )

    def latest_version(self, template_id: str) -> ReportTemplateVersion | None:
        return self.db.execute(
            select(ReportTemplateVersion)
            .where(ReportTemplateVersion.template_id == template_id)
            .order_by(ReportTemplateVersion.version_no.desc())
            .limit(1)
        ).scalars().first()

    def delete_template(self, template: ReportTemplate) -> None:
        from app.db.metadata import ReportSchedule

        template.current_published_version_id = None
        self.db.flush()
        self.db.query(ReportSchedule).filter(ReportSchedule.template_id == template.id).delete()
        self.db.query(ReportTemplateVersion).filter(
            ReportTemplateVersion.template_id == template.id
        ).delete()
        self.db.delete(template)
        self.db.flush()

    def get_published_version(self, template_id: str) -> ReportTemplateVersion | None:
        tpl = self.db.get(ReportTemplate, template_id)
        if tpl is None or tpl.current_published_version_id is None:
            return None
        return self.db.get(ReportTemplateVersion, tpl.current_published_version_id)

    def set_published(self, template_id: str, version_id: str) -> None:
        tpl = self.db.get(ReportTemplate, template_id)
        if tpl is not None:
            tpl.current_published_version_id = version_id
            self.db.flush()
