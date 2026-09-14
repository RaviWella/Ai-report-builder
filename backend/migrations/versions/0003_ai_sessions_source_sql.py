"""ai_sessions: add source_sql (legacy-SQL grounding for the rule-report chat)

Revision ID: 0003_ai_sessions_source_sql
Revises: 0002_ai_sessions_rule_chat
Create Date: 2026-08-25
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_ai_sessions_source_sql"
down_revision = "0002_ai_sessions_rule_chat"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ai_sessions", sa.Column("source_sql", sa.Text(), nullable=True))
    op.add_column("ai_sessions", sa.Column("source_sql_filename", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("ai_sessions", "source_sql_filename")
    op.drop_column("ai_sessions", "source_sql")
