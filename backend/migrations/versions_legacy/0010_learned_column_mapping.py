"""learned column mapping (remember header -> field corrections)

Revision ID: 0010_learned_column_mapping
Revises: 0009_chat_session_title
Create Date: 2026-07-02
"""
from alembic import op
import sqlalchemy as sa

revision = "0010_learned_column_mapping"
down_revision = "0009_chat_session_title"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "learned_column_mapping",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("header_key", sa.String(255), nullable=False),
        sa.Column("header_sample", sa.String(255), nullable=False),
        sa.Column("ref", sa.String(255), nullable=True),  # NULL = remembered skip
        sa.Column("hits", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_used_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "header_key", name="uq_learned_col_header"),
    )
    op.create_index("ix_learned_column_mapping_tenant_id", "learned_column_mapping", ["tenant_id"])
    op.create_index("ix_learned_column_mapping_header_key", "learned_column_mapping", ["header_key"])


def downgrade() -> None:
    op.drop_index("ix_learned_column_mapping_header_key", table_name="learned_column_mapping")
    op.drop_index("ix_learned_column_mapping_tenant_id", table_name="learned_column_mapping")
    op.drop_table("learned_column_mapping")
