"""document studio: template lifecycle status

Revision ID: 0014_template_status
Revises: 0013_document_categories
Create Date: 2026-07-08
"""
from alembic import op
import sqlalchemy as sa

revision = "0014_template_status"
down_revision = "0013_document_categories"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "report_templates",
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
    )
    op.create_index("ix_report_templates_status", "report_templates", ["status"])
    # Existing published documents/reports -> 'active' so they aren't hidden as drafts.
    op.execute(
        "UPDATE report_templates SET status='active' WHERE current_published_version_id IS NOT NULL"
    )


def downgrade() -> None:
    op.drop_index("ix_report_templates_status", table_name="report_templates")
    op.drop_column("report_templates", "status")
