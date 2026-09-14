"""Document application service — the Document Studio backend.

A document is a report_template whose version presentation_spec is a document
envelope:
    {
      "kind": "document",
      "doc_type": "letter" | "email" | "report",
      "category": <str>,                     # tenant category (also mirrored to module)
      "document": <DocumentSpec>,            # doc_type="report" (structured payslip/statement)
      "design":   <DocumentDesign>,          # doc_type="letter"|"email" (canvas blocks)
      "email":    {"subject": <str>},        # doc_type="email"
      "allowed_formats": [...],
    }
plus a DERIVED data_spec (the bound refs + scope runtime params) so versioning, the
semantic-version pin, publish and audit all work unchanged.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.tenancy import TenantContext
from app.domain.document_design import DocumentDesign
from app.domain.document_spec import DocumentSpec
from app.domain.enums import FilterOp, ParamType
from app.domain.report_spec import DataSpec, FieldSelection, FilterClause, RuntimeParam
from app.repositories.template_repo import TemplateRepo
from app.services.ai_service import AIService
from app.services.document_ingestion import DocumentDraft, build_document_from_excel
from app.services.document_sample import bind_word_merge_fields
from app.services.document_design_render import (
    compose_labelled,
    generate_letters,
    generate_letters_docx,
    preview_email,
    preview_letter_html,
)
from app.services.document_render import generate_documents
from app.services.semantic_service import SemanticService

DOCUMENT_KIND = "document"
DOC_TYPES = ("letter", "email", "report")


def _require_publishable(
    publish: bool, name: str, category: str, doc_type: str, design: DocumentDesign | None,
) -> None:
    """BR-T-01/02: a name and category are required to publish; a draft can't be issued
    with them blank. A letter also can't publish without 'One per record' set — HRIS
    issues letters per employee, and the ref must come from the designer's own choice
    on the tenant's catalogue, never a guessed default (Report Builder is a generic
    platform; the ref can't be assumed the same across tenants)."""
    if publish and not (name or "").strip():
        raise ValueError("A name is required to publish.")
    if publish and not (category or "").strip():
        raise ValueError("A category is required to publish.")
    if publish and doc_type == "letter" and not (design and design.record_key_ref):
        raise ValueError("Set 'One per record' before publishing this letter.")


class DocumentService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = TemplateRepo(db)
        self.semantic = SemanticService(db)
        self.ai = AIService(db)

    # ---- ingest (Excel -> structured report-doc draft) --------------------- #
    def ingest(self, ctx: TenantContext, content: bytes) -> DocumentDraft:
        return build_document_from_excel(self.ai, ctx, content)

    # ---- derived data_spec (per-record query + scope filter bar) ----------- #
    def _derived_data_spec(
        self, ctx: TenantContext, *, value_refs: list[str],
        year_ref: str | None, month_ref: str | None, key_ref: str | None,
    ) -> DataSpec:
        labels = self.semantic.get_active_catalog(ctx.tenant_id).field_index()
        params: list[RuntimeParam] = []
        filters: list[FilterClause] = []

        def label_of(ref: str, fallback: str) -> str:
            f = labels.get(ref)
            return f.label if f and f.label else fallback

        if year_ref and month_ref:
            params.append(RuntimeParam(name="doc_year", type=ParamType.NUMBER, required=True,
                                       label=label_of(year_ref, "Year")))
            params.append(RuntimeParam(name="doc_month", type=ParamType.NUMBER, required=True,
                                       label=label_of(month_ref, "Month")))
            filters.append(FilterClause(ref=year_ref, op=FilterOp.EQ, param="doc_year"))
            filters.append(FilterClause(ref=month_ref, op=FilterOp.EQ, param="doc_month"))
        if key_ref:
            params.append(RuntimeParam(name="doc_record", type=ParamType.STRING, required=False,
                                       label=label_of(key_ref, "Record")))
            filters.append(FilterClause(ref=key_ref, op=FilterOp.EQ, param="doc_record"))

        return DataSpec(
            entity="employee",
            fields=[FieldSelection(ref=r, label=r) for r in value_refs],
            filters=filters,
            runtime_params=params,
        )

    def _derived_for(self, ctx: TenantContext, *, document: DocumentSpec | None,
                     design: DocumentDesign | None) -> DataSpec:
        if design is not None:
            return self._derived_data_spec(
                ctx, value_refs=design.value_refs(), year_ref=design.period_year_ref,
                month_ref=design.period_month_ref, key_ref=design.record_key_ref,
            )
        spec = document or DocumentSpec()
        return self._derived_data_spec(
            ctx, value_refs=spec.value_refs(), year_ref=spec.period_year_ref,
            month_ref=spec.period_month_ref, key_ref=spec.record_key_ref,
        )

    @staticmethod
    def _default_formats(doc_type: str) -> list[str]:
        return ["email"] if doc_type == "email" else ["pdf"]

    def _presentation(
        self, *, doc_type: str, category: str | None,
        document: DocumentSpec | None, design: DocumentDesign | None,
        email_subject: str | None, allowed_formats: list[str] | None,
    ) -> dict:
        ps: dict[str, Any] = {
            "kind": DOCUMENT_KIND,
            "doc_type": doc_type,
            "category": category,
            "allowed_formats": allowed_formats or self._default_formats(doc_type),
        }
        if document is not None:
            ps["document"] = document.model_dump(mode="json")
        if design is not None:
            ps["design"] = design.model_dump(mode="json")
        if doc_type == "email":
            ps["email"] = {"subject": email_subject or ""}
        return ps

    # ---- create / update --------------------------------------------------- #
    def create(
        self, ctx: TenantContext, *, name: str, category: str, doc_type: str,
        document: DocumentSpec | None = None, design: DocumentDesign | None = None,
        email_subject: str | None = None, publish: bool = False,
        allowed_formats: list[str] | None = None,
    ) -> dict:
        if doc_type not in DOC_TYPES:
            raise ValueError(f"Unknown document type {doc_type!r}")
        _require_publishable(publish, name, category, doc_type, design)
        catalog = self.semantic.get_active_catalog(ctx.tenant_id)
        tpl = self.repo.create_template(
            name=name, description=None,
            created_by=ctx.acting_user_id, module=category or "General",
        )
        version = self.repo.add_version(
            template_id=tpl.id,
            data_spec=self._derived_for(ctx, document=document, design=design).model_dump(mode="json"),
            presentation_spec=self._presentation(
                doc_type=doc_type, category=category, document=document, design=design,
                email_subject=email_subject, allowed_formats=allowed_formats,
            ),
            semantic_version_ref=catalog.version,
            status="published" if publish else "draft",
            created_by=ctx.acting_user_id,
        )
        if publish:
            self.repo.set_published(tpl.id, version.id)
            tpl.status = "active"
        self.db.commit()
        return self._saved(version, tpl.id)

    def update(
        self, ctx: TenantContext, template_id: str, *, name: str, category: str, doc_type: str,
        document: DocumentSpec | None = None, design: DocumentDesign | None = None,
        email_subject: str | None = None, publish: bool = False,
        allowed_formats: list[str] | None = None,
    ) -> dict:
        if doc_type not in DOC_TYPES:
            raise ValueError(f"Unknown document type {doc_type!r}")
        _require_publishable(publish, name, category, doc_type, design)
        tpl = self.repo.get_template(template_id)
        if tpl is None:
            raise ValueError("Document not found for this tenant.")
        tpl.name = name
        tpl.module = category or "General"
        catalog = self.semantic.get_active_catalog(ctx.tenant_id)
        version = self.repo.add_version(
            template_id=tpl.id,
            data_spec=self._derived_for(ctx, document=document, design=design).model_dump(mode="json"),
            presentation_spec=self._presentation(
                doc_type=doc_type, category=category, document=document, design=design,
                email_subject=email_subject, allowed_formats=allowed_formats,
            ),
            semantic_version_ref=catalog.version,
            status="published" if publish else "draft",
            created_by=ctx.acting_user_id,
        )
        if publish:
            self.repo.set_published(tpl.id, version.id)
            tpl.status = "active"
        self.db.commit()
        return self._saved(version, tpl.id)

    def set_status(self, ctx: TenantContext, template_id: str, status: str) -> dict:
        """Move a document through its lifecycle: active | inactive | archived | draft."""
        if status not in ("active", "inactive", "archived", "draft"):
            raise ValueError(f"Unknown status {status!r}")
        tpl = self.repo.get_template(template_id)
        if tpl is None:
            raise ValueError("Document not found for this tenant.")
        tpl.status = status
        self.db.commit()
        return {"id": tpl.id, "status": tpl.status}

    # ---- read -------------------------------------------------------------- #
    def _load(self, ctx: TenantContext, template_id: str):
        tpl = self.repo.get_template(template_id)
        if tpl is None:
            raise ValueError("Document not found for this tenant.")
        ver = self.repo.get_published_version(template_id) or self.repo.latest_version(template_id)
        ps = (ver.presentation_spec if ver else None) or {}
        if ps.get("kind") != DOCUMENT_KIND:
            raise ValueError("Not a document template.")
        return tpl, ver, ps

    def get(self, ctx: TenantContext, template_id: str) -> dict:
        tpl, ver, ps = self._load(ctx, template_id)
        design = ps.get("design")
        record_key_ref = None
        if isinstance(design, dict):
            # A letter published before publish-time validation required this (see
            # _require_publishable) may still have it blank — that's surfaced as-is,
            # not patched with a guessed ref; HRIS Create Letter's own "no record key"
            # message is the correct prompt to fix the letter's design, not this code.
            record_key_ref = design.get("record_key_ref") or None
        return {
            "id": tpl.id, "name": tpl.name,
            "category": ps.get("category") or tpl.module,
            "doc_type": ps.get("doc_type", "report"),
            "status": tpl.status or ("active" if ver and ver.status == "published" else "draft"),
            "allowed_formats": ps.get("allowed_formats") or ["pdf"],
            "document": ps.get("document"),
            "design": design,
            "record_key_ref": record_key_ref,
            "email_subject": (ps.get("email") or {}).get("subject", ""),
        }

    def list(self, ctx: TenantContext, doc_type: str | None = None) -> list[dict]:
        out: list[dict] = []
        for t in self.repo.list_templates():
            ver = self.repo.get_published_version(t.id) or self.repo.latest_version(t.id)
            ps = (ver.presentation_spec or {}) if ver else {}
            if ps.get("kind") != DOCUMENT_KIND:
                continue
            dt = ps.get("doc_type", "report")
            if doc_type and dt != doc_type:
                continue
            out.append({
                "id": t.id, "name": t.name,
                "description": t.description or "",
                "category": ps.get("category") or t.module,
                "doc_type": dt, "status": t.status or ("active" if ver and ver.status == "published" else "draft"),
                "version_no": ver.version_no if ver else 0,
                "updated_at": ver.created_at.isoformat() if ver and ver.created_at else None,
            })
        return out

    def duplicate(self, ctx: TenantContext, template_id: str) -> dict:
        """Copy an existing document as a new DRAFT (start-from: copy existing)."""
        tpl, ver, ps = self._load(ctx, template_id)
        if ver is None:
            raise ValueError("Nothing to copy — this document has no saved version yet.")
        catalog = self.semantic.get_active_catalog(ctx.tenant_id)
        new_tpl = self.repo.create_template(
            name=f"{tpl.name} (copy)", description=tpl.description,
            created_by=ctx.acting_user_id, module=tpl.module,
        )
        version = self.repo.add_version(
            template_id=new_tpl.id,
            data_spec=dict(ver.data_spec or {}),
            presentation_spec=dict(ps),
            semantic_version_ref=catalog.version,
            status="draft",
            created_by=ctx.acting_user_id,
        )
        self.db.commit()
        return self._saved(version, new_tpl.id)

    # ---- render / preview -------------------------------------------------- #
    def render(
        self, ctx: TenantContext, template_id: str, *,
        year: int | None = None, month: int | None = None,
        record_key: str | None = None, max_records: int | None = None,
        manual: dict[str, str] | None = None, fmt: str = "pdf",
    ) -> bytes:
        tpl, ver, ps = self._load(ctx, template_id)
        if ver is None:
            raise ValueError("This document has no saved version.")
        catalog = self.semantic.get_pinned_catalog(ctx.tenant_id, ver.semantic_version_ref)
        dmk = self._datamart_key(ctx.tenant_id)
        doc_type = ps.get("doc_type", "report")
        if fmt == "docx":
            # Editable Word — supported for canvas letters (the designer's own output).
            if doc_type != "letter":
                raise ValueError("Word download is available for letters.")
            design = bind_word_merge_fields(DocumentDesign.model_validate(ps["design"]), catalog)
            return generate_letters_docx(
                ctx, dmk, catalog, design,
                year=year, month=month, record_key=record_key, max_records=max_records,
                manual=manual,
            )
        if doc_type == "report":
            spec = DocumentSpec.model_validate(ps["document"])
            return generate_documents(
                ctx, dmk, catalog, spec,
                year=year, month=month, record_key=record_key, max_records=max_records,
            )
        if doc_type == "letter":
            design = bind_word_merge_fields(DocumentDesign.model_validate(ps["design"]), catalog)
            return generate_letters(
                ctx, dmk, catalog, design,
                year=year, month=month, record_key=record_key, max_records=max_records,
                manual=manual,
            )
        raise ValueError("Emails are preview-only; use the preview endpoint.")

    def preview(
        self, ctx: TenantContext, template_id: str, *,
        year: int | None = None, month: int | None = None, record_key: str | None = None,
        labelled: bool = False, manual: dict[str, str] | None = None,
    ) -> dict:
        tpl, ver, ps = self._load(ctx, template_id)
        if ver is None:
            raise ValueError("This document has no saved version.")
        catalog = self.semantic.get_pinned_catalog(ctx.tenant_id, ver.semantic_version_ref)
        dmk = self._datamart_key(ctx.tenant_id)
        doc_type = ps.get("doc_type", "report")
        design_json = ps.get("design")
        if not design_json:
            raise ValueError("Preview is available for letter/email documents.")
        design = bind_word_merge_fields(DocumentDesign.model_validate(design_json), catalog)
        # Labelled preview (AC-TC-05): tokens shown as [Field Label], no data query.
        if labelled:
            labels = catalog.field_index()
            _SYS = {"system.date": "Today’s date", "system.date_iso": "Today’s date",
                    "system.year": "Current year", "system.month": "Current month",
                    "system.day": "Current day"}

            def label_of(ref: str) -> str:
                if ref in _SYS:
                    return _SYS[ref]
                f = labels.get(ref)
                return f.label if f and f.label else ref.split(".")[-1]

            html = compose_labelled(design, label_of)
            subject = (ps.get("email") or {}).get("subject", "") if doc_type == "email" else None
            return {"doc_type": doc_type, "html": html, "subject": subject, "record_count": 0}
        if doc_type == "email":
            subject = (ps.get("email") or {}).get("subject", "")
            return {"doc_type": "email", **preview_email(
                ctx, dmk, catalog, design, subject=subject,
                year=year, month=month, record_key=record_key, manual=manual,
            )}
        return {"doc_type": "letter", **preview_letter_html(
            ctx, dmk, catalog, design, year=year, month=month, record_key=record_key, manual=manual,
        )}

    @staticmethod
    def _saved(version: Any, template_id: str) -> dict:
        return {
            "template_id": template_id, "version_id": version.id,
            "version_no": version.version_no, "status": version.status,
        }

    def _datamart_key(self, tenant_id: str) -> str:
        from app.services.tenant_scope import resolve_datamart_key

        return resolve_datamart_key(tenant_id)
