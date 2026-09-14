"""Add tenant_custom_reports — per-tenant report metadata in application DB.

Revision ID: 0014_tenant_custom_reports
Revises: 0013_clear_registry_sources
Create Date: 2026-06-05
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect, text

revision: str = "0014_tenant_custom_reports"
down_revision: Union[str, None] = "0013_clear_registry_sources"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "hrm_control"


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)

    if "tenant_custom_reports" not in insp.get_table_names(schema=_SCHEMA):
        op.create_table(
            "tenant_custom_reports",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("tenant_id", sa.String(length=128), nullable=False),
            sa.Column("module", sa.String(length=64), nullable=False),
            sa.Column("report_name", sa.String(length=255), nullable=False),
            sa.Column("view_name", sa.String(length=128), nullable=False),
            sa.Column("view_query", sa.Text(), nullable=True),
            sa.Column(
                "report_type",
                sa.String(length=32),
                nullable=False,
                server_default="table",
            ),
            sa.Column(
                "source",
                sa.String(length=16),
                nullable=False,
                server_default="sync",
            ),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=True,
            ),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("tenant_id", "view_name", name="uq_tenant_custom_reports_view"),
            schema=_SCHEMA,
        )
        op.create_index(
            "ix_tenant_custom_reports_tenant_module",
            "tenant_custom_reports",
            ["tenant_id", "module", "is_active"],
            unique=False,
            schema=_SCHEMA,
        )

    # Report rows and SQL are seeded in 0015_custom_reports_db_managed.


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if "tenant_custom_reports" not in insp.get_table_names(schema=_SCHEMA):
        return
    op.drop_index(
        "ix_tenant_custom_reports_tenant_module",
        table_name="tenant_custom_reports",
        schema=_SCHEMA,
    )
    op.drop_table("tenant_custom_reports", schema=_SCHEMA)
