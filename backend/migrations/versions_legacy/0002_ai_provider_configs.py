"""ai provider configs (encrypted UI-entered AI keys)

Revision ID: 0002_ai_configs
Revises: 0001_initial
Create Date: 2026-06-06
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_ai_configs"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_provider_configs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column("provider", sa.String(32), nullable=False, server_default="anthropic"),
        sa.Column("model", sa.String(128), nullable=False, server_default="claude-opus-4-8"),
        sa.Column("base_url", sa.String(255)),
        sa.Column("api_key_encrypted", sa.Text),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("updated_by", sa.String(64), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("ai_provider_configs")
