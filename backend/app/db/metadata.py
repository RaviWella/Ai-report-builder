"""Metadata DB: ORM models + tenant-scoped tables (Architecture §6).

Schema-per-tenant isolation: tables live in each tenant schema (cloned from public).
Tenant tables have NO tenant_id column — isolation is enforced via SET search_path.
Platform control-plane tables live in app.db.platform_models.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Re-export platform models for Alembic metadata registration.
from app.db.platform_models import (  # noqa: F401
    PlatformBase,
    SystemAIProviderConfig,
    TenantProvisionStatus,
)


def _uuid() -> str:
    return str(uuid.uuid4())


class PostgresBase(DeclarativeBase):
    """Base for tenant-scoped tables (no hard-coded schema — search_path at runtime)."""


Base = PostgresBase


class SemanticModel(PostgresBase):
    """Versioned semantic layer (catalog JSONB). Pinned by report versions."""

    __tablename__ = "semantic_models"
    __table_args__ = (UniqueConstraint("version", name="uq_semantic_version"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    version: Mapped[int] = mapped_column(Integer)
    catalog: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReportTemplate(PostgresBase):
    __tablename__ = "report_templates"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    module: Mapped[str] = mapped_column(String(64), default="General", index=True)
    status: Mapped[str] = mapped_column(String(16), default="draft", index=True)
    current_published_version_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_by: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    versions: Mapped[list[ReportTemplateVersion]] = relationship(
        back_populates="template", cascade="all, delete-orphan"
    )


class ReportTemplateVersion(PostgresBase):
    __tablename__ = "report_template_versions"
    __table_args__ = (UniqueConstraint("template_id", "version_no", name="uq_template_version_no"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    template_id: Mapped[str] = mapped_column(ForeignKey("report_templates.id"), index=True)
    version_no: Mapped[int] = mapped_column(Integer)
    data_spec: Mapped[dict] = mapped_column(JSONB)
    presentation_spec: Mapped[dict] = mapped_column(JSONB)
    semantic_version_ref: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="draft")
    created_by: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    template: Mapped[ReportTemplate] = relationship(back_populates="versions")


class TemplateUpload(PostgresBase):
    __tablename__ = "template_uploads"
    template_id: Mapped[str] = mapped_column(
        ForeignKey("report_templates.id", ondelete="CASCADE"), primary_key=True
    )
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(128), default="application/octet-stream")
    content_enc: Mapped[bytes] = mapped_column(LargeBinary)
    size_bytes: Mapped[int] = mapped_column(Integer)
    created_by: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DocumentCategory(PostgresBase):
    __tablename__ = "document_categories"
    __table_args__ = (UniqueConstraint("doc_type", "name", name="uq_doc_category"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    doc_type: Mapped[str] = mapped_column(String(16), index=True)
    name: Mapped[str] = mapped_column(String(120))
    created_by: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Letterhead(PostgresBase):
    __tablename__ = "letterheads"
    __table_args__ = (UniqueConstraint("name", name="uq_letterhead_name"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(120))
    logo_data_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    header_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    footer_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ManualField(PostgresBase):
    __tablename__ = "manual_fields"
    __table_args__ = (UniqueConstraint("key", name="uq_manual_field_key"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    key: Mapped[str] = mapped_column(String(80))
    label: Mapped[str] = mapped_column(String(160))
    created_by: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReportSchedule(PostgresBase):
    __tablename__ = "report_schedules"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    template_id: Mapped[str] = mapped_column(ForeignKey("report_templates.id"), index=True)
    cron: Mapped[str] = mapped_column(String(120))
    recipients: Mapped[list] = mapped_column(JSONB, default=list)
    format: Mapped[str] = mapped_column(String(8), default="pdf")
    runtime_params: Mapped[dict] = mapped_column(JSONB, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AISession(PostgresBase):
    __tablename__ = "ai_sessions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    template_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    title: Mapped[str | None] = mapped_column(String(160), nullable=True)
    # Discriminates which builder this session belongs to (default "data_spec"
    # keeps every pre-existing row valid without a backfill). "rule_report"
    # sessions use working_rule_spec instead of working_data_spec.
    kind: Mapped[str] = mapped_column(String(32), server_default="data_spec")
    messages: Mapped[list] = mapped_column(JSONB, default=list)
    working_data_spec: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    working_rule_spec: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Sample sheet upload (rule-report AI chat): HEADERS + inferred type only, same
    # privacy rule as the Excel mapping AI (app/ingestion/excel_parser.py) — the
    # actual data rows are never persisted here or sent to the AI.
    sample_sheet_headers: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    sample_sheet_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Legacy source SQL (e.g. the old MySQL report this rule report replaces) —
    # plain text, structure/logic only, no data rows, so no encryption needed
    # (same treatment as sample_sheet_headers). Resent every chat turn as
    # grounding for mapping old table/column names to the new datamart.
    source_sql: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_sql_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_by: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AISessionAttachment(PostgresBase):
    """The requirement DOC (image/PDF screenshot) for a rule-report AI chat
    session — encrypted at rest, same pattern as TemplateUpload. Unlike the
    sample sheet (headers only), a requirement doc's actual content (layout,
    wording) is exactly what the AI needs to read, so it's kept in full — just
    encrypted, one per session (re-uploading replaces it)."""

    __tablename__ = "ai_session_attachments"
    session_id: Mapped[str] = mapped_column(
        ForeignKey("ai_sessions.id", ondelete="CASCADE"), primary_key=True
    )
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(128), default="application/octet-stream")
    content_enc: Mapped[bytes] = mapped_column(LargeBinary)
    size_bytes: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AIProviderConfig(PostgresBase):
    __tablename__ = "ai_provider_configs"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    provider: Mapped[str] = mapped_column(String(32), default="anthropic")
    model: Mapped[str] = mapped_column(String(128), default="claude-opus-4-8")
    base_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_by: Mapped[str] = mapped_column(String(64))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AuditLog(PostgresBase):
    __tablename__ = "audit_log"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(64))
    target_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    detail: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class SqlCache(PostgresBase):
    __tablename__ = "sql_cache"
    version_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    sql_text: Mapped[str] = mapped_column(Text)
    semantic_version_ref: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReportRun(PostgresBase):
    __tablename__ = "report_runs"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    report_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    semantic_version_ref: Mapped[int | None] = mapped_column(Integer, nullable=True)
    compiled_sql_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    result_checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)
    datamart_snapshot_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="ok")
    fmt: Mapped[str | None] = mapped_column(String(16), nullable=True)
    executed_by: Mapped[str] = mapped_column(String(64))
    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class MartValidationResult(PostgresBase):
    __tablename__ = "mart_validation_result"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    validation_run_id: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(80), index=True)
    category: Mapped[str] = mapped_column(String(24))
    severity: Mapped[str] = mapped_column(String(12))
    status: Mapped[str] = mapped_column(String(8))
    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class SemanticMetric(PostgresBase):
    __tablename__ = "semantic_metrics"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    key: Mapped[str] = mapped_column(String(80), index=True)
    definition: Mapped[dict] = mapped_column(JSONB)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SemanticGlossary(PostgresBase):
    __tablename__ = "semantic_glossary"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    term_key: Mapped[str] = mapped_column(String(120), index=True)
    definition: Mapped[dict] = mapped_column(JSONB)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LearnedIntent(PostgresBase):
    __tablename__ = "learned_intent"
    __table_args__ = (UniqueConstraint("phrase_key", name="uq_learned_intent_phrase"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    phrase_key: Mapped[str] = mapped_column(String(255), index=True)
    phrase_sample: Mapped[str] = mapped_column(Text)
    spec: Mapped[dict] = mapped_column(JSONB)
    signature: Mapped[str] = mapped_column(String(64), index=True)
    source: Mapped[str] = mapped_column(String(16), default="deterministic")
    certified: Mapped[bool] = mapped_column(Boolean, default=False)
    hits: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LearnedColumnMapping(PostgresBase):
    __tablename__ = "learned_column_mapping"
    __table_args__ = (UniqueConstraint("header_key", name="uq_learned_col_header"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    header_key: Mapped[str] = mapped_column(String(255), index=True)
    header_sample: Mapped[str] = mapped_column(String(255))
    ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    hits: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FieldRequest(PostgresBase):
    __tablename__ = "field_request"
    __table_args__ = (UniqueConstraint("header_key", name="uq_field_request_header"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    header_key: Mapped[str] = mapped_column(String(255), index=True)
    header_sample: Mapped[str] = mapped_column(String(255))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="open")
    hits: Mapped[int] = mapped_column(Integer, default=1)
    requested_by: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

