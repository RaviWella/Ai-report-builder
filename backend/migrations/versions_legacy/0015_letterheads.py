"""document studio: per-tenant letterhead presets

Revision ID: 0015_letterheads
Revises: 0014_template_status
Create Date: 2026-07-08
"""
from alembic import op
import sqlalchemy as sa

revision = "0015_letterheads"
down_revision = "0014_template_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "letterheads",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("logo_data_url", sa.Text(), nullable=True),
        sa.Column("header_html", sa.Text(), nullable=True),
        sa.Column("footer_html", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.UniqueConstraint("tenant_id", "name", name="uq_letterhead_name"),
    )
    op.create_index("ix_letterheads_tenant_id", "letterheads", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_letterheads_tenant_id", table_name="letterheads")
    op.drop_table("letterheads")
