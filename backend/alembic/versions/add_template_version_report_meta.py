"""Add extra_result_blocks and report_layout to datamart_template_versions

Revision ID: tpl_version_report_meta_001
Revises: add_datamart_report_layout_001
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "tpl_version_report_meta_001"
down_revision: Union[str, None] = "add_datamart_report_layout_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "datamart_template_versions",
        sa.Column(
            "extra_result_blocks",
            JSONB,
            nullable=True,
            comment="Additional scenario SQL blocks (same shape as chat messages).",
        ),
    )
    op.add_column(
        "datamart_template_versions",
        sa.Column(
            "report_layout",
            JSONB,
            nullable=True,
            comment="Report canvas layout v1 (view mode, widgets, scenario labels).",
        ),
    )


def downgrade() -> None:
    op.drop_column("datamart_template_versions", "report_layout")
    op.drop_column("datamart_template_versions", "extra_result_blocks")
