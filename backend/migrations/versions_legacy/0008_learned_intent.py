"""canonical-intent / learning store

Revision ID: 0008_learned_intent
Revises: 0007_semantic_glossary
Create Date: 2026-06-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0008_learned_intent"
down_revision = "0007_semantic_glossary"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "learned_intent",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("phrase_key", sa.String(255), nullable=False),
        sa.Column("phrase_sample", sa.Text(), nullable=False),
        sa.Column("spec", JSONB(), nullable=False),
        sa.Column("signature", sa.String(64), nullable=False),
        sa.Column("source", sa.String(16), nullable=False, server_default="deterministic"),
        sa.Column("certified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("hits", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_used_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "phrase_key", name="uq_learned_intent_phrase"),
    )
    op.create_index("ix_learned_intent_tenant_id", "learned_intent", ["tenant_id"])
    op.create_index("ix_learned_intent_phrase_key", "learned_intent", ["phrase_key"])
    op.create_index("ix_learned_intent_signature", "learned_intent", ["signature"])


def downgrade() -> None:
    op.drop_index("ix_learned_intent_signature", table_name="learned_intent")
    op.drop_index("ix_learned_intent_phrase_key", table_name="learned_intent")
    op.drop_index("ix_learned_intent_tenant_id", table_name="learned_intent")
    op.drop_table("learned_intent")
