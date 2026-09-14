"""WS-1 report run lineage (run log + checksums)

Revision ID: 0004_report_runs
Revises: 0003_template_module
Create Date: 2026-06-12
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_report_runs"
down_revision = "0003_template_module"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "report_runs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("report_id", sa.String(64), nullable=True),
        sa.Column("semantic_version_ref", sa.Integer(), nullable=True),
        sa.Column("compiled_sql_hash", sa.String(64), nullable=True),
        sa.Column("result_checksum", sa.String(64), nullable=True),
        sa.Column("datamart_snapshot_ref", sa.String(128), nullable=True),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="ok"),
        sa.Column("fmt", sa.String(16), nullable=True),
        sa.Column("executed_by", sa.String(64), nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_report_runs_tenant_id", "report_runs", ["tenant_id"])
    op.create_index("ix_report_runs_report_id", "report_runs", ["report_id"])
    op.create_index("ix_report_runs_executed_at", "report_runs", ["executed_at"])


def downgrade() -> None:
    op.drop_index("ix_report_runs_executed_at", table_name="report_runs")
    op.drop_index("ix_report_runs_report_id", table_name="report_runs")
    op.drop_index("ix_report_runs_tenant_id", table_name="report_runs")
    op.drop_table("report_runs")
