"""business glossary tier

Revision ID: 0007_semantic_glossary
Revises: 0006_semantic_metrics
Create Date: 2026-06-12
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0007_semantic_glossary"
down_revision = "0006_semantic_metrics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "semantic_glossary",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("term_key", sa.String(120), nullable=False),
        sa.Column("definition", JSONB(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_semantic_glossary_tenant_id", "semantic_glossary", ["tenant_id"])
    op.create_index("ix_semantic_glossary_term_key", "semantic_glossary", ["term_key"])


def downgrade() -> None:
    op.drop_index("ix_semantic_glossary_term_key", table_name="semantic_glossary")
    op.drop_index("ix_semantic_glossary_tenant_id", table_name="semantic_glossary")
    op.drop_table("semantic_glossary")
