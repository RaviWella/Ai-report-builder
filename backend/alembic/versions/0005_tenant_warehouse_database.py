"""Add per-tenant warehouse database columns to tenant_registry.

Revision ID: 0005
Revises: 0004
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if "tenant_registry" not in insp.get_table_names(schema="hrm_control"):
        return
    cols = {c["name"] for c in insp.get_columns("tenant_registry", schema="hrm_control")}
    for name, col in (
        ("warehouse_host", sa.Column("warehouse_host", sa.String(length=255), nullable=True)),
        ("warehouse_port", sa.Column("warehouse_port", sa.Integer(), nullable=True)),
        ("warehouse_db", sa.Column("warehouse_db", sa.String(length=128), nullable=True)),
        ("warehouse_user", sa.Column("warehouse_user", sa.String(length=255), nullable=True)),
        (
            "warehouse_password_enc",
            sa.Column("warehouse_password_enc", sa.Text(), nullable=True),
        ),
    ):
        if name not in cols:
            op.add_column("tenant_registry", col, schema="hrm_control")
    op.execute(
        """
        UPDATE hrm_control.tenant_registry
        SET warehouse_db = 'hrm_wh_' || tenant_id
        WHERE warehouse_db IS NULL
        """
    )


def downgrade() -> None:
    op.drop_column("tenant_registry", "warehouse_password_enc", schema="hrm_control")
    op.drop_column("tenant_registry", "warehouse_user", schema="hrm_control")
    op.drop_column("tenant_registry", "warehouse_db", schema="hrm_control")
    op.drop_column("tenant_registry", "warehouse_port", schema="hrm_control")
    op.drop_column("tenant_registry", "warehouse_host", schema="hrm_control")
