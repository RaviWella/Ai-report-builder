"""
Datamart Workspace Models
==========================
Four tables that implement session groups, templates, template versions,
and template groups for the Datamart AI Chat feature.

Tables:
  datamart_session_groups     — named folders for grouping chat sessions
  datamart_templates          — saved query templates promoted from chat
  datamart_template_versions  — immutable snapshots of a template at a point in time
  datamart_template_groups    — named folders for grouping templates

Design decisions:
  - All tables live in the **public** schema (not per-org schema copies)
  - UUID primary keys throughout (auth-ready)
  - user_id TEXT — accepts any format, hardcoded to 'default-user' until auth is wired
  - Templates store the full response payload (sql, post_process_config, narrative)
    so every version is fully self-contained and re-executable
  - is_latest flag on versions avoids expensive MAX(version_num) queries
  - group_id on sessions and templates is nullable — ungrouped items are valid
  - Cascade deletes: deleting a group does NOT delete its children (SET NULL)
    so sessions/templates are never accidentally lost
  - template_session_id on DatamartTemplate links to a hidden chat session used
    for the template's own modify-chat history (not shown in the chat sidebar)
"""
import uuid
from sqlalchemy import (
    Column, String, Text, Boolean, Integer,
    DateTime, ForeignKey, Index, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func

from app.core.database import Base


# ── Session Groups ────────────────────────────────────────────────

class DatamartSessionGroup(Base):
    """
    A named folder that can contain multiple chat sessions.

    Deleting a group sets group_id=NULL on its sessions (SET NULL),
    so sessions are never lost when a group is removed.
    """
    __tablename__ = "datamart_session_groups"
    __table_args__ = (
        Index("ix_dsg_user_id", "user_id"),
        Index("ix_datamart_session_groups_tenant_user", "tenant_id", "user_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    tenant_id = Column(String(128), nullable=False, server_default="demo_tenant", index=True)
    user_id = Column(String(255), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    position = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Display order within the sidebar (ascending).",
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


# ── Template Groups ───────────────────────────────────────────────

class DatamartTemplateGroup(Base):
    """
    A named folder that can contain multiple templates.
    Same SET NULL cascade behaviour as DatamartSessionGroup.
    """
    __tablename__ = "datamart_template_groups"
    __table_args__ = (
        Index("ix_dtg_user_id", "user_id"),
        Index("ix_datamart_template_groups_tenant_user", "tenant_id", "user_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    tenant_id = Column(String(128), nullable=False, server_default="demo_tenant", index=True)
    user_id = Column(String(255), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    position = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


# ── Templates ─────────────────────────────────────────────────────

class DatamartTemplate(Base):
    """
    A saved query template promoted from a chat response.

    A template is a named container for versioned query results.
    The actual data (SQL, post-processing, narrative) lives in
    DatamartTemplateVersion rows.
    """
    __tablename__ = "datamart_templates"
    __table_args__ = (
        Index("ix_dt_user_id", "user_id"),
        Index("ix_dt_group_id", "group_id"),
        Index("ix_dt_updated_at", "updated_at"),
        Index("ix_datamart_templates_tenant_user", "tenant_id", "user_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    tenant_id = Column(String(128), nullable=False, server_default="demo_tenant", index=True)
    user_id = Column(String(255), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    group_id = Column(
        UUID(as_uuid=True),
        ForeignKey("datamart_template_groups.id", ondelete="SET NULL"),
        nullable=True,
        comment="Optional group. NULL = ungrouped.",
    )
    is_pinned = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Pinned templates appear at the top of the sidebar.",
    )
    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Soft-delete flag.",
    )
    template_session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("datamart_chat_sessions.id", ondelete="SET NULL"),
        nullable=True,
        comment="Session used for interactive template modification.",
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


# ── Template Versions ─────────────────────────────────────────────

class DatamartTemplateVersion(Base):
    """
    An immutable snapshot of a template at a specific point in time.

    Versions are created explicitly by the user ("Save as Version").
    Each version stores the complete response payload so it is fully
    self-contained and re-executable without any external dependencies.

    Lineage:
      source_session_id / source_message_id — which chat message this
      version was originally promoted from (v1 only; subsequent versions
      are NULL for these fields).

    is_latest:
      True for the most recently created version of a template.
      Updated atomically when a new version is saved.
      Only one version per template should have is_latest=True at any time.
    """
    __tablename__ = "datamart_template_versions"
    __table_args__ = (
        Index("ix_dtv_template_id", "template_id"),
        Index("ix_dtv_template_latest", "template_id", "is_latest"),
        UniqueConstraint("template_id", "version_num", name="uq_dtv_template_version"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    template_id = Column(
        UUID(as_uuid=True),
        ForeignKey("datamart_templates.id", ondelete="CASCADE"),
        nullable=False,
    )
    version_num = Column(
        Integer,
        nullable=False,
        comment="Sequential version number within the template (1-based).",
    )
    label = Column(
        String(255),
        nullable=True,
        comment="Optional user-given label e.g. 'Added department column'.",
    )
    # ── Full response payload ─────────────────────────────────────
    sql_script = Column(
        Text,
        nullable=False,
        comment="The SQL query that produces this version's data.",
    )
    post_process_config = Column(
        JSONB,
        nullable=True,
        comment="Optional post-processing steps applied after SQL execution.",
    )
    chart_configs = Column(
        JSONB,
        nullable=True,
        comment="Optional chart specs (same schema as datamart_chat_messages.chart_configs).",
    )
    extra_result_blocks = Column(
        JSONB,
        nullable=True,
        comment="Additional scenario SQL blocks (same JSON shape as datamart_chat_messages).",
    )
    report_layout = Column(
        JSONB,
        nullable=True,
        comment="Report canvas layout v1 for multi-scenario templates.",
    )
    narrative = Column(
        Text,
        nullable=True,
        comment="Plain-English description of what this version shows.",
    )
    # ── Lineage ───────────────────────────────────────────────────
    source_session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("datamart_chat_sessions.id", ondelete="SET NULL"),
        nullable=True,
        comment="Chat session this version was promoted from (v1 only).",
    )
    source_message_id = Column(
        UUID(as_uuid=True),
        ForeignKey("datamart_chat_messages.id", ondelete="SET NULL"),
        nullable=True,
        comment="Chat message this version was promoted from (v1 only).",
    )
    # ── State ─────────────────────────────────────────────────────
    is_latest = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="True for the most recently saved version of this template.",
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
