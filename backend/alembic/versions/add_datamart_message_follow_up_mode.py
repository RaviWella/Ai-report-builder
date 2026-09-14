"""Add follow_up_mode to datamart_chat_messages (user turns)

Revision ID: add_datamart_follow_up_mode_001
Revises: add_datamart_extra_blocks_001
Create Date: 2026-05-18

Records whether a user message was continue_last (modify prior result) or
new_question when sent — used for undo-last-modification.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "add_datamart_follow_up_mode_001"
down_revision: Union[str, None] = "add_datamart_extra_blocks_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "datamart_chat_messages",
        sa.Column(
            "follow_up_mode",
            sa.String(32),
            nullable=True,
            comment="User turn only: continue_last | new_question",
        ),
    )


def downgrade() -> None:
    op.drop_column("datamart_chat_messages", "follow_up_mode")
