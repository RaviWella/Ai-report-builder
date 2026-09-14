"""ai_sessions: add kind discriminator + working_rule_spec (AI rule-report chat)

Revision ID: 0002_ai_sessions_rule_chat
Revises: 0001_schema_per_tenant_baseline
Create Date: 2026-08-25
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0002_ai_sessions_rule_chat"
down_revision = "0001_schema_per_tenant_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ai_sessions",
        sa.Column("kind", sa.String(32), server_default="data_spec", nullable=False),
    )
    op.add_column(
        "ai_sessions",
        sa.Column("working_rule_spec", JSONB(), nullable=True),
    )
    op.add_column(
        "ai_sessions",
        sa.Column("sample_sheet_headers", JSONB(), nullable=True),
    )
    op.add_column(
        "ai_sessions",
        sa.Column("sample_sheet_filename", sa.String(255), nullable=True),
    )
    op.create_table(
        "ai_session_attachments",
        sa.Column("session_id", sa.String(64),
                  sa.ForeignKey("ai_sessions.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(128), server_default="application/octet-stream", nullable=False),
        sa.Column("content_enc", sa.LargeBinary(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("ai_session_attachments")
    op.drop_column("ai_sessions", "sample_sheet_filename")
    op.drop_column("ai_sessions", "sample_sheet_headers")
    op.drop_column("ai_sessions", "working_rule_spec")
    op.drop_column("ai_sessions", "kind")
