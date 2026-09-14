"""Add validation JSONB to datamart_chat_messages

Revision ID: 0010_dm_msg_validation
Revises: 0009_datamart_tenant_id
Create Date: 2026-05-25

Stores retrieval/generation validation snapshot on assistant turns.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0010_dm_msg_validation"
down_revision: Union[str, None] = "0010_datamart_tenant_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "datamart_chat_messages",
        sa.Column(
            "validation",
            JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Retrieval and generation validation snapshot (trust badge, sources, warnings).",
        ),
    )


def downgrade() -> None:
    op.drop_column("datamart_chat_messages", "validation")
