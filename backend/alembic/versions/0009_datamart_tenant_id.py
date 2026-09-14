"""Add tenant_id to datamart workspace tables for multi-tenant isolation.

Revision ID: 0009_datamart_tenant_id
Revises: 0008
Create Date: 2026-05-22

Backfills existing rows with demo_tenant (dev default until auth is wired).
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009_datamart_tenant_id"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DEFAULT_TENANT = "demo_tenant"

_TABLES = (
    "datamart_chat_sessions",
    "datamart_session_groups",
    "datamart_template_groups",
    "datamart_templates",
)


def upgrade() -> None:
    for table in _TABLES:
        op.add_column(
            table,
            sa.Column(
                "tenant_id",
                sa.String(128),
                nullable=True,
                comment="MintHRM tenant id (X-Tenant-Id); isolates workspace per customer.",
            ),
        )
        op.execute(
            sa.text(
                f"UPDATE {table} SET tenant_id = :tid WHERE tenant_id IS NULL"
            ).bindparams(tid=_DEFAULT_TENANT)
        )
        op.alter_column(
            table,
            "tenant_id",
            nullable=False,
            server_default=_DEFAULT_TENANT,
        )
        op.create_index(
            f"ix_{table}_tenant_user",
            table,
            ["tenant_id", "user_id"],
        )


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.drop_index(f"ix_{table}_tenant_user", table_name=table)
        op.drop_column(table, "tenant_id")
