"""Create hrm_control schema and tenant_registry table.

Revision ID: 0001
Revises:
Create Date: 2026-05-18

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS hrm_control")

    bind = op.get_bind()
    insp = inspect(bind)
    schema = "hrm_control"
    if "tenant_registry" not in insp.get_table_names(schema=schema):
        op.create_table(
            "tenant_registry",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("tenant_id", sa.String(length=128), nullable=False),
            sa.Column("display_name", sa.String(length=255), nullable=False),
            sa.Column("source_type", sa.String(length=32), nullable=False, server_default="mysql"),
            sa.Column("mysql_host", sa.String(length=255), nullable=False),
            sa.Column("mysql_port", sa.Integer(), nullable=False, server_default="3306"),
            sa.Column("mysql_db", sa.String(length=255), nullable=False),
            sa.Column("mysql_user", sa.String(length=255), nullable=False),
            sa.Column("mysql_password_enc", sa.Text(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
            sa.Column("last_etl_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=True,
            ),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("tenant_id"),
            schema=schema,
        )
        insp = inspect(bind)

    if "tenant_registry" not in insp.get_table_names(schema=schema):
        return

    idx_id = op.f("ix_hrm_control_tenant_registry_id")
    if not any(
        i.get("name") == idx_id
        for i in insp.get_indexes("tenant_registry", schema=schema)
    ):
        op.create_index(idx_id, "tenant_registry", ["id"], unique=False, schema=schema)

    idx_tid = op.f("ix_hrm_control_tenant_registry_tenant_id")
    if not any(
        i.get("name") == idx_tid
        for i in insp.get_indexes("tenant_registry", schema=schema)
    ):
        op.create_index(
            idx_tid, "tenant_registry", ["tenant_id"], unique=True, schema=schema
        )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_hrm_control_tenant_registry_tenant_id"),
        table_name="tenant_registry",
        schema="hrm_control",
    )
    op.drop_index(
        op.f("ix_hrm_control_tenant_registry_id"),
        table_name="tenant_registry",
        schema="hrm_control",
    )
    op.drop_table("tenant_registry", schema="hrm_control")
    op.execute("DROP SCHEMA IF EXISTS hrm_control")
