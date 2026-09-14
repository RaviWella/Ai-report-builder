"""Template lifecycle service (SRS §7, README §6).

Implements the versioning model:
  - autosave drafts continuously (save_draft mutates the open draft version)
  - create an immutable version snapshot only on publish (D7)
  - each version pins the semantic version it was built against (SRS §7.3)
  - rollback = re-publish any previous version

The data + presentation specs are validated against the Pydantic models and the
active semantic catalogue before a draft is accepted, so a publish can never
snapshot an unresolvable spec.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.tenancy import TenantContext
from app.db.metadata import ReportTemplate, ReportTemplateVersion
from app.domain.enums import AuditAction, VersionStatus
from app.domain.report_spec import DataSpec, PresentationSpec
from app.query_engine import guards
from app.repositories.template_repo import TemplateRepo
from app.services.audit_service import AuditService
from app.services.semantic_service import SemanticService


@dataclass
class DraftInput:
    data_spec: DataSpec
    presentation_spec: PresentationSpec


class TemplateService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = TemplateRepo(db)
        self.semantic = SemanticService(db)
        self.audit = AuditService(db)

    # --- create ---
    def create_template(
        self, ctx: TenantContext, *, name: str, description: str | None, module: str = "General"
    ) -> ReportTemplate:
        tpl = self.repo.create_template(
            name=name, description=description,
            created_by=ctx.acting_user_id, module=module,
        )
        self.db.commit()
        self.audit.log(
            user_id=ctx.acting_user_id,
            action=AuditAction.TEMPLATE_CREATED,
            target_type="template",
            target_id=tpl.id,
            detail={"name": name},
        )
        return tpl

    def rename(
        self, ctx: TenantContext, template_id: str, name: str | None = None,
        module: str | None = None, description: str | None = None,
    ) -> ReportTemplate:
        tpl = self._owned_template(ctx, template_id)
        if name and name.strip():
            tpl.name = name.strip()
        if module and module.strip():
            tpl.module = module.strip()
        if description is not None:  # "" clears it
            tpl.description = description.strip() or None
        self.db.commit()
        self.audit.log(
            user_id=ctx.acting_user_id,
            action=AuditAction.TEMPLATE_UPDATED, target_type="template", target_id=tpl.id,
            detail={"renamed_to": tpl.name},
        )
        return tpl

    # --- draft (autosave) ---
    def save_draft(self, ctx: TenantContext, template_id: str, draft: DraftInput) -> ReportTemplateVersion:
        tpl = self._owned_template(ctx, template_id)
        catalog = self.semantic.get_active_catalog(ctx.tenant_id)

        # Validate the spec resolves against the active catalogue before persisting.
        guards.validate_refs(draft.data_spec, catalog)
        guards.validate_joins(draft.data_spec, catalog)

        # Keep the template name in sync with the report title the user typed.
        title = (draft.presentation_spec.title or "").strip()
        if title and title != tpl.name:
            tpl.name = title

        version = self.repo.add_version(
            template_id=tpl.id,
            data_spec=draft.data_spec.model_dump(mode="json"),
            presentation_spec=draft.presentation_spec.model_dump(mode="json"),
            semantic_version_ref=catalog.version,
            status=VersionStatus.DRAFT.value,
            created_by=ctx.acting_user_id,
        )
        self.db.commit()
        self.audit.log(
            user_id=ctx.acting_user_id,
            action=AuditAction.TEMPLATE_UPDATED,
            target_type="template_version",
            target_id=version.id,
            detail={"version_no": version.version_no, "status": "draft"},
        )
        return version

    # --- publish (immutable snapshot) ---
    def publish(self, ctx: TenantContext, template_id: str, version_id: str) -> ReportTemplateVersion:
        tpl = self._owned_template(ctx, template_id)
        version = self.repo.get_version(tpl.id, version_id)
        if version is None:
            raise ValueError("Version not found")
        version.status = VersionStatus.PUBLISHED.value
        self.repo.set_published(tpl.id, version.id)
        self.db.commit()
        self.audit.log(
            user_id=ctx.acting_user_id,
            action=AuditAction.VERSION_PUBLISHED,
            target_type="template_version",
            target_id=version.id,
            detail={"version_no": version.version_no, "semantic_version_ref": version.semantic_version_ref},
        )
        return version

    # --- rollback (re-publish a previous version) ---
    def rollback(self, ctx: TenantContext, template_id: str, version_id: str) -> ReportTemplateVersion:
        tpl = self._owned_template(ctx, template_id)
        version = self.repo.get_version(tpl.id, version_id)
        if version is None:
            raise ValueError("Version not found")
        self.repo.set_published(tpl.id, version.id)
        self.db.commit()
        self.audit.log(
            user_id=ctx.acting_user_id,
            action=AuditAction.VERSION_ROLLED_BACK,
            target_type="template_version",
            target_id=version.id,
            detail={"version_no": version.version_no},
        )
        return version

    def latest_spec(self, ctx: TenantContext, template_id: str):
        """The template + its most recent saved version — used to LOAD a report
        back into the builder for editing. Tenant-scoped."""
        tpl = self._owned_template(ctx, template_id)
        return tpl, self.repo.latest_version(template_id)

    def delete_template(self, ctx: TenantContext, template_id: str) -> None:
        """Delete a report (and its versions/schedules) — tenant-scoped."""
        tpl = self._owned_template(ctx, template_id)
        self.repo.delete_template(tpl)
        self.audit.log(
            user_id=ctx.acting_user_id,
            action=AuditAction.TEMPLATE_DELETED,
            target_type="template",
            target_id=template_id,
        )

    def _owned_template(self, ctx: TenantContext, template_id: str) -> ReportTemplate:
        tpl = self.repo.get_template(template_id)
        if tpl is None:
            raise ValueError("Template not found for this tenant")
        return tpl
