"""canonical metrics layer

Revision ID: 0006_semantic_metrics
Revises: 0005_validation_result
Create Date: 2026-06-12
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0006_semantic_metrics"
down_revision = "0005_validation_result"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "semantic_metrics",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("key", sa.String(80), nullable=False),
        sa.Column("definition", JSONB(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_semantic_metrics_tenant_id", "semantic_metrics", ["tenant_id"])
    op.create_index("ix_semantic_metrics_key", "semantic_metrics", ["key"])


def downgrade() -> None:
    op.drop_index("ix_semantic_metrics_key", table_name="semantic_metrics")
    op.drop_index("ix_semantic_metrics_tenant_id", table_name="semantic_metrics")
    op.drop_table("semantic_metrics")
