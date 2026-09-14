"""Repair tenant_registry and warehouse columns when migrations were stamped partially.

Extends 0006: creates hrm_control.tenant_registry when missing and adds
warehouse_* columns from 0005 when absent.

Revision ID: 0007
Revises: 0006
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(insp, schema: str | None, name: str) -> bool:
    return name in insp.get_table_names(schema=schema)


def _registry_columns(insp) -> set[str]:
    if not _has_table(insp, "hrm_control", "tenant_registry"):
        return set()
    return {c["name"] for c in insp.get_columns("tenant_registry", schema="hrm_control")}


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS hrm_control")

    bind = op.get_bind()
    insp = inspect(bind)

    if not _has_table(insp, "hrm_control", "tenant_registry"):
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
            sa.Column("source_connection_id", sa.Integer(), nullable=True),
            sa.Column("warehouse_host", sa.String(length=255), nullable=True),
            sa.Column("warehouse_port", sa.Integer(), nullable=True),
            sa.Column("warehouse_db", sa.String(length=128), nullable=True),
            sa.Column("warehouse_user", sa.String(length=255), nullable=True),
            sa.Column("warehouse_password_enc", sa.Text(), nullable=True),
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
            schema="hrm_control",
        )
        op.create_index(
            op.f("ix_hrm_control_tenant_registry_id"),
            "tenant_registry",
            ["id"],
            unique=False,
            schema="hrm_control",
        )
        op.create_index(
            op.f("ix_hrm_control_tenant_registry_tenant_id"),
            "tenant_registry",
            ["tenant_id"],
            unique=True,
            schema="hrm_control",
        )
        insp = inspect(bind)

    reg_cols = _registry_columns(insp)
    if not reg_cols:
        return

    column_adds = [
        ("source_connection_id", sa.Column("source_connection_id", sa.Integer(), nullable=True)),
        ("warehouse_host", sa.Column("warehouse_host", sa.String(length=255), nullable=True)),
        ("warehouse_port", sa.Column("warehouse_port", sa.Integer(), nullable=True)),
        ("warehouse_db", sa.Column("warehouse_db", sa.String(length=128), nullable=True)),
        ("warehouse_user", sa.Column("warehouse_user", sa.String(length=255), nullable=True)),
        (
            "warehouse_password_enc",
            sa.Column("warehouse_password_enc", sa.Text(), nullable=True),
        ),
    ]
    for name, col in column_adds:
        if name not in reg_cols:
            op.add_column("tenant_registry", col, schema="hrm_control")

    op.execute(
        """
        UPDATE hrm_control.tenant_registry
        SET warehouse_db = 'hrm_wh_' || tenant_id
        WHERE warehouse_db IS NULL
        """
    )


def downgrade() -> None:
    pass
