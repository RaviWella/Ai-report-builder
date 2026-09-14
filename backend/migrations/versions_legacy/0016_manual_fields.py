"""document studio: per-tenant reusable manual-field pool

Revision ID: 0016_manual_fields
Revises: 0015_letterheads
Create Date: 2026-07-09
"""
from alembic import op
import sqlalchemy as sa

revision = "0016_manual_fields"
down_revision = "0015_letterheads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "manual_fields",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("key", sa.String(80), nullable=False),
        sa.Column("label", sa.String(160), nullable=False),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.UniqueConstraint("tenant_id", "key", name="uq_manual_field_key"),
    )
    op.create_index("ix_manual_fields_tenant_id", "manual_fields", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_manual_fields_tenant_id", table_name="manual_fields")
    op.drop_table("manual_fields")
