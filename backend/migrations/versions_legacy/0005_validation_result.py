"""WS-3 data-quality validation results

Revision ID: 0005_validation_result
Revises: 0004_report_runs
Create Date: 2026-06-12
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0005_validation_result"
down_revision = "0004_report_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mart_validation_result",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("validation_run_id", sa.String(64), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("category", sa.String(24), nullable=False),
        sa.Column("severity", sa.String(12), nullable=False),
        sa.Column("status", sa.String(8), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("details", JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_mvr_tenant_id", "mart_validation_result", ["tenant_id"])
    op.create_index("ix_mvr_run_id", "mart_validation_result", ["validation_run_id"])
    op.create_index("ix_mvr_name", "mart_validation_result", ["name"])
    op.create_index("ix_mvr_created_at", "mart_validation_result", ["created_at"])


def downgrade() -> None:
    for ix in ("ix_mvr_created_at", "ix_mvr_name", "ix_mvr_run_id", "ix_mvr_tenant_id"):
        op.drop_index(ix, table_name="mart_validation_result")
    op.drop_table("mart_validation_result")
