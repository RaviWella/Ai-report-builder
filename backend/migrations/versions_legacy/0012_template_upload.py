"""template source-file store (encrypted at rest)

Revision ID: 0012_template_upload
Revises: 0011_field_request
Create Date: 2026-07-07
"""
from alembic import op
import sqlalchemy as sa

revision = "0012_template_upload"
down_revision = "0011_field_request"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "template_uploads",
        sa.Column("template_id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(128), nullable=False, server_default="application/octet-stream"),
        sa.Column("content_enc", sa.LargeBinary(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["template_id"], ["report_templates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
    )
    op.create_index("ix_template_uploads_tenant_id", "template_uploads", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_template_uploads_tenant_id", table_name="template_uploads")
    op.drop_table("template_uploads")
