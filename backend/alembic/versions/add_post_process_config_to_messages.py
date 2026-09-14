"""Add post_process_config column to datamart_chat_messages

Revision ID: add_post_process_config_001
Revises: add_datamart_chat_001
Create Date: 2026-05-13

Adds a JSONB column to store Python post-processing instructions for
assistant messages. This enables derived calculations (e.g. add a
percentage column, append a summary row) that cannot be expressed in
a single SQL query.

The column is nullable — existing rows without post-processing are
unaffected. When present, the backend applies the steps to the SQL
result before returning to the frontend, and re-applies them on
"Run Query" so historical results are always reproducible.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "add_post_process_config_001"
down_revision: Union[str, None] = "add_datamart_chat_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "datamart_chat_messages",
        sa.Column(
            "post_process_config",
            JSONB,
            nullable=True,
            comment=(
                "Optional JSON array of post-processing steps applied to the SQL result. "
                "Each step: {type, ...params}. "
                "Supported types: add_percentage_column, append_aggregate_row, add_derived_column."
            ),
        ),
    )


def downgrade() -> None:
    op.drop_column("datamart_chat_messages", "post_process_config")
