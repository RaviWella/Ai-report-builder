"""Add source_connection_id to tenant_registry.

Allows a tenant to point their ETL source at a saved DatabaseConnection
record instead of the legacy mysql_* inline fields.

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-18
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if "tenant_registry" not in insp.get_table_names(schema="hrm_control"):
        return
    cols = {c["name"] for c in insp.get_columns("tenant_registry", schema="hrm_control")}
    if "source_connection_id" not in cols:
        op.add_column(
            "tenant_registry",
            sa.Column("source_connection_id", sa.Integer(), nullable=True),
            schema="hrm_control",
        )


def downgrade() -> None:
    op.drop_column("tenant_registry", "source_connection_id", schema="hrm_control")
