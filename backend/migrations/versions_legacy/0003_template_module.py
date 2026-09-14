"""report template module/category

Revision ID: 0003_template_module
Revises: 0002_ai_configs
Create Date: 2026-06-07
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_template_module"
down_revision = "0002_ai_configs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "report_templates",
        sa.Column("module", sa.String(64), nullable=False, server_default="General"),
    )
    op.create_index("ix_report_templates_module", "report_templates", ["module"])


def downgrade() -> None:
    op.drop_index("ix_report_templates_module", table_name="report_templates")
    op.drop_column("report_templates", "module")
