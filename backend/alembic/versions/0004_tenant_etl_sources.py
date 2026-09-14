"""Add tenant_etl_sources — multiple ETL sources per tenant.

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-18
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    schema = "hrm_control"
    if "tenant_etl_sources" not in insp.get_table_names(schema=schema):
        op.create_table(
            "tenant_etl_sources",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("tenant_id", sa.String(length=128), nullable=False),
            sa.Column("source_key", sa.String(length=64), nullable=False),
            sa.Column("display_name", sa.String(length=255), nullable=False),
            sa.Column("source_type", sa.String(length=32), nullable=False, server_default="mysql"),
            sa.Column("connection_id", sa.Integer(), nullable=True),
            sa.Column("source_schema", sa.String(length=255), nullable=True),
            sa.Column("extractor_profile", sa.String(length=64), nullable=False, server_default="minthrm"),
            sa.Column("mapping_variant", sa.String(length=32), nullable=True),
            sa.Column("is_primary", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
            sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=True,
            ),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("tenant_id", "source_key", name="uq_tenant_etl_sources_key"),
            schema=schema,
        )
        insp = inspect(bind)

    if "tenant_etl_sources" in insp.get_table_names(schema=schema) and not any(
        i.get("name") == "ix_tenant_etl_sources_tenant_id"
        for i in insp.get_indexes("tenant_etl_sources", schema=schema)
    ):
        op.create_index(
            "ix_tenant_etl_sources_tenant_id",
            "tenant_etl_sources",
            ["tenant_id"],
            unique=False,
            schema=schema,
        )


def downgrade() -> None:
    op.drop_index(
        "ix_tenant_etl_sources_tenant_id",
        table_name="tenant_etl_sources",
        schema="hrm_control",
    )
    op.drop_table("tenant_etl_sources", schema="hrm_control")
