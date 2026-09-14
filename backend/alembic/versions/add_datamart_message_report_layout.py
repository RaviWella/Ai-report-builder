"""Add report_layout JSONB to datamart_chat_messages

Revision ID: add_datamart_report_layout_001
Revises: add_datamart_follow_up_mode_001
Create Date: 2026-05-18

Stores per-message report canvas layout, scenario labels, and export visibility.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "add_datamart_report_layout_001"
down_revision: Union[str, None] = "add_datamart_follow_up_mode_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "datamart_chat_messages",
        sa.Column(
            "report_layout",
            JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Report canvas: scenario labels, widget grid, export flags (schema v1).",
        ),
    )


def downgrade() -> None:
    op.drop_column("datamart_chat_messages", "report_layout")
