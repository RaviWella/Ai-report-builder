"""Add datamart chat sessions, messages, and summaries tables

Revision ID: add_datamart_chat_001
Revises: 0004
Create Date: 2026-05-13

Creates three tables for the Datamart AI Chat feature:
  - datamart_chat_sessions   : one row per conversation session per user
  - datamart_chat_messages   : one row per message turn (user or assistant)
  - datamart_chat_summaries  : rolling LLM summaries of old turns for context management
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID


revision: str = "add_datamart_chat_001"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. datamart_chat_sessions ─────────────────────────────────
    op.create_table(
        "datamart_chat_sessions",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", sa.String(255), nullable=False),
        sa.Column(
            "title",
            sa.String(255),
            nullable=False,
            server_default="New conversation",
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_dcs_user_id", "datamart_chat_sessions", ["user_id"])
    op.create_index("ix_dcs_updated_at", "datamart_chat_sessions", ["updated_at"])

    # ── 2. datamart_chat_messages ─────────────────────────────────
    op.create_table(
        "datamart_chat_messages",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "session_id",
            UUID(as_uuid=True),
            sa.ForeignKey("datamart_chat_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("sql_script", sa.Text(), nullable=True),
        sa.Column("question_ref", sa.Text(), nullable=True),
        sa.Column("turn_index", sa.Integer(), nullable=False),
        sa.Column(
            "is_summarised",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("role IN ('user', 'assistant')", name="ck_dcm_role"),
    )
    op.create_index("ix_dcm_session_id", "datamart_chat_messages", ["session_id"])
    op.create_index(
        "ix_dcm_session_turn",
        "datamart_chat_messages",
        ["session_id", "turn_index"],
    )

    # ── 3. datamart_chat_summaries ────────────────────────────────
    op.create_table(
        "datamart_chat_summaries",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "session_id",
            UUID(as_uuid=True),
            sa.ForeignKey("datamart_chat_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("summary_text", sa.Text(), nullable=False),
        sa.Column("covers_up_to_turn", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_dcs_sum_session_id", "datamart_chat_summaries", ["session_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_dcs_sum_session_id", "datamart_chat_summaries")
    op.drop_table("datamart_chat_summaries")

    op.drop_index("ix_dcm_session_turn", "datamart_chat_messages")
    op.drop_index("ix_dcm_session_id", "datamart_chat_messages")
    op.drop_table("datamart_chat_messages")

    op.drop_index("ix_dcs_updated_at", "datamart_chat_sessions")
    op.drop_index("ix_dcs_user_id", "datamart_chat_sessions")
    op.drop_table("datamart_chat_sessions")
