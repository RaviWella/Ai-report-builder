"""document studio: per-tenant document categories

Revision ID: 0013_document_categories
Revises: 0012_template_upload
Create Date: 2026-07-07
"""
from alembic import op
import sqlalchemy as sa

revision = "0013_document_categories"
down_revision = "0012_template_upload"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_categories",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("doc_type", sa.String(16), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.UniqueConstraint("tenant_id", "doc_type", "name", name="uq_doc_category"),
    )
    op.create_index("ix_document_categories_tenant_id", "document_categories", ["tenant_id"])
    op.create_index("ix_document_categories_doc_type", "document_categories", ["doc_type"])


def downgrade() -> None:
    op.drop_index("ix_document_categories_doc_type", table_name="document_categories")
    op.drop_index("ix_document_categories_tenant_id", table_name="document_categories")
    op.drop_table("document_categories")
