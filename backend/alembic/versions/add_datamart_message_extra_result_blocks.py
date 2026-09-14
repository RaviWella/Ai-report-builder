"""Add extra_result_blocks JSONB to datamart_chat_messages

Revision ID: add_datamart_extra_blocks_001
Revises: add_datamart_chart_configs_001
Create Date: 2026-05-15

Stores metadata for additional SQL result sets in the same assistant turn
(block_id, title, sql_script, post_process_config). Rows are not persisted;
clients re-execute via the blocks execute API.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "add_datamart_extra_blocks_001"
down_revision: Union[str, None] = "add_datamart_chart_configs_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "datamart_chat_messages",
        sa.Column(
            "extra_result_blocks",
            JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Additional SQL blocks in same turn: [{block_id, title, sql_script, post_process_config}, ...]",
        ),
    )


def downgrade() -> None:
    op.drop_column("datamart_chat_messages", "extra_result_blocks")
