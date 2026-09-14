"""initial metadata schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-06
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("datamart_key", sa.String(128), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("tenants.id"), index=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "semantic_models",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("tenants.id"), index=True),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("catalog", JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "version", name="uq_semantic_tenant_version"),
    )
    op.create_table(
        "report_templates",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("tenants.id"), index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("current_published_version_id", sa.String(64)),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "report_template_versions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("template_id", sa.String(64), sa.ForeignKey("report_templates.id"), index=True),
        sa.Column("version_no", sa.Integer, nullable=False),
        sa.Column("data_spec", JSONB, nullable=False),
        sa.Column("presentation_spec", JSONB, nullable=False),
        sa.Column("semantic_version_ref", sa.Integer, nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("template_id", "version_no", name="uq_template_version_no"),
    )
    op.create_table(
        "report_schedules",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("template_id", sa.String(64), sa.ForeignKey("report_templates.id"), index=True),
        sa.Column("cron", sa.String(120), nullable=False),
        sa.Column("recipients", JSONB, server_default="[]"),
        sa.Column("format", sa.String(8), server_default="pdf"),
        sa.Column("runtime_params", JSONB, server_default="{}"),
        sa.Column("enabled", sa.Boolean, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "ai_sessions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("template_id", sa.String(64), index=True),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("tenants.id"), index=True),
        sa.Column("messages", JSONB, server_default="[]"),
        sa.Column("working_data_spec", JSONB),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "audit_log",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(64), index=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("target_type", sa.String(64)),
        sa.Column("target_id", sa.String(64)),
        sa.Column("detail", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), index=True),
    )
    op.create_table(
        "sql_cache",
        sa.Column("version_id", sa.String(64), primary_key=True),
        sa.Column("sql_text", sa.Text, nullable=False),
        sa.Column("semantic_version_ref", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    for tbl in (
        "sql_cache", "audit_log", "ai_sessions", "report_schedules",
        "report_template_versions", "report_templates", "semantic_models",
        "users", "tenants",
    ):
        op.drop_table(tbl)
