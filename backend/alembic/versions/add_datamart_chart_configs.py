"""Add chart_configs JSONB to datamart messages and template versions

Revision ID: add_datamart_chart_configs_001
Revises: add_template_session_id_001
Create Date: 2026-05-14

Stores declarative chart definitions (Recharts-oriented schema v1) per assistant
message and per template version — no image blobs.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "add_datamart_chart_configs_001"
down_revision: Union[str, None] = "add_template_session_id_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "datamart_chat_messages",
        sa.Column(
            "chart_configs",
            JSONB,
            nullable=True,
            comment="Ordered list of chart spec objects (schema_version=1). Rendered client-side.",
        ),
    )
    op.add_column(
        "datamart_template_versions",
        sa.Column(
            "chart_configs",
            JSONB,
            nullable=True,
            comment="Charts promoted with template version; same schema as datamart_chat_messages.",
        ),
    )


def downgrade() -> None:
    op.drop_column("datamart_template_versions", "chart_configs")
    op.drop_column("datamart_chat_messages", "chart_configs")
