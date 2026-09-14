"""Add datamart workspace tables (session groups, templates, template versions, template groups)

Revision ID: add_datamart_workspace_001
Revises: add_post_process_config_001
Create Date: 2026-05-13

Creates:
  - datamart_session_groups     : named folders for grouping chat sessions
  - datamart_template_groups    : named folders for grouping templates
  - datamart_templates          : saved query templates promoted from chat
  - datamart_template_versions  : immutable versioned snapshots of templates

Modifies:
  - datamart_chat_sessions      : adds group_id FK (nullable, SET NULL on group delete)

Note on cascade behaviour:
  - Deleting a session group sets group_id=NULL on its sessions (SET NULL)
  - Deleting a template group sets group_id=NULL on its templates (SET NULL)
  - Deleting a template cascades to its versions (CASCADE)
  - Deleting a session/message sets source FK to NULL on template versions (SET NULL)
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID, JSONB


revision: str = "add_datamart_workspace_001"
down_revision: Union[str, None] = "add_post_process_config_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. datamart_session_groups ────────────────────────────────
    op.create_table(
        "datamart_session_groups",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_dsg_user_id", "datamart_session_groups", ["user_id"])

    # ── 2. datamart_template_groups ───────────────────────────────
    op.create_table(
        "datamart_template_groups",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_dtg_user_id", "datamart_template_groups", ["user_id"])

    # ── 3. datamart_templates ─────────────────────────────────────
    op.create_table(
        "datamart_templates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("group_id", UUID(as_uuid=True),
                  sa.ForeignKey("datamart_template_groups.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("is_pinned", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_dt_user_id", "datamart_templates", ["user_id"])
    op.create_index("ix_dt_group_id", "datamart_templates", ["group_id"])
    op.create_index("ix_dt_updated_at", "datamart_templates", ["updated_at"])

    # ── 4. datamart_template_versions ────────────────────────────
    op.create_table(
        "datamart_template_versions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("template_id", UUID(as_uuid=True),
                  sa.ForeignKey("datamart_templates.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("version_num", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(255), nullable=True),
        sa.Column("sql_script", sa.Text(), nullable=False),
        sa.Column("post_process_config", JSONB, nullable=True),
        sa.Column("narrative", sa.Text(), nullable=True),
        sa.Column("source_session_id", UUID(as_uuid=True),
                  sa.ForeignKey("datamart_chat_sessions.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("source_message_id", UUID(as_uuid=True),
                  sa.ForeignKey("datamart_chat_messages.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("is_latest", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("template_id", "version_num",
                            name="uq_dtv_template_version"),
    )
    op.create_index("ix_dtv_template_id", "datamart_template_versions", ["template_id"])
    op.create_index("ix_dtv_template_latest", "datamart_template_versions",
                    ["template_id", "is_latest"])

    # ── 5. Add group_id to datamart_chat_sessions ─────────────────
    op.add_column(
        "datamart_chat_sessions",
        sa.Column("group_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_dcs_group_id",
        "datamart_chat_sessions",
        "datamart_session_groups",
        ["group_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_dcs_group_id", "datamart_chat_sessions", ["group_id"])


def downgrade() -> None:
    # Reverse in dependency order
    op.drop_index("ix_dcs_group_id", "datamart_chat_sessions")
    op.drop_constraint("fk_dcs_group_id", "datamart_chat_sessions", type_="foreignkey")
    op.drop_column("datamart_chat_sessions", "group_id")

    op.drop_index("ix_dtv_template_latest", "datamart_template_versions")
    op.drop_index("ix_dtv_template_id", "datamart_template_versions")
    op.drop_table("datamart_template_versions")

    op.drop_index("ix_dt_updated_at", "datamart_templates")
    op.drop_index("ix_dt_group_id", "datamart_templates")
    op.drop_index("ix_dt_user_id", "datamart_templates")
    op.drop_table("datamart_templates")

    op.drop_index("ix_dtg_user_id", "datamart_template_groups")
    op.drop_table("datamart_template_groups")

    op.drop_index("ix_dsg_user_id", "datamart_session_groups")
    op.drop_table("datamart_session_groups")
