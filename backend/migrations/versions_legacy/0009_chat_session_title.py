"""chat session title (ChatGPT-style history)

Revision ID: 0009_chat_session_title
Revises: 0008_learned_intent
Create Date: 2026-06-30
"""
from alembic import op
import sqlalchemy as sa

revision = "0009_chat_session_title"
down_revision = "0008_learned_intent"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ai_sessions", sa.Column("title", sa.String(160), nullable=True))


def downgrade() -> None:
    op.drop_column("ai_sessions", "title")
