"""field request (data-capture / ETL gap list)

Revision ID: 0011_field_request
Revises: 0010_learned_column_mapping
Create Date: 2026-07-02
"""
from alembic import op
import sqlalchemy as sa

revision = "0011_field_request"
down_revision = "0010_learned_column_mapping"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "field_request",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("header_key", sa.String(255), nullable=False),
        sa.Column("header_sample", sa.String(255), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="open"),
        sa.Column("hits", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("requested_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_requested_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("tenant_id", "header_key", name="uq_field_request_header"),
    )
    op.create_index("ix_field_request_tenant_id", "field_request", ["tenant_id"])
    op.create_index("ix_field_request_header_key", "field_request", ["header_key"])


def downgrade() -> None:
    op.drop_index("ix_field_request_header_key", table_name="field_request")
    op.drop_index("ix_field_request_tenant_id", table_name="field_request")
    op.drop_table("field_request")
