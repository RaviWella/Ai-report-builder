"""Add database_connections and data_access_rules tables.

These tables live in the public schema (template) and are cloned into each
tenant's mart schema by TenantManager.ensure_schemas_exist().

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-18
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)

    if "database_connections" not in insp.get_table_names(schema="public"):
        op.create_table(
            "database_connections",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("engine", sa.String(length=50), nullable=False),
            sa.Column("host", sa.String(length=500), nullable=False),
            sa.Column("port", sa.Integer(), nullable=False),
            sa.Column("database_name", sa.String(length=255), nullable=False),
            sa.Column("username", sa.String(length=255), nullable=False),
            sa.Column("password_encrypted", sa.Text(), nullable=False),
            sa.Column("default_schema", sa.String(length=255), nullable=True),
            sa.Column("ssl_mode", sa.String(length=50), nullable=True),
            sa.Column("connection_options", sa.JSON(), nullable=True),
            sa.Column("ssh_enabled", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("ssh_host", sa.String(length=500), nullable=True),
            sa.Column("ssh_port", sa.Integer(), nullable=True),
            sa.Column("ssh_username", sa.String(length=255), nullable=True),
            sa.Column("ssh_auth_method", sa.String(length=20), nullable=True),
            sa.Column("ssh_password_encrypted", sa.Text(), nullable=True),
            sa.Column("ssh_private_key_encrypted", sa.Text(), nullable=True),
            sa.Column("ssh_key_passphrase_encrypted", sa.Text(), nullable=True),
            sa.Column("ssh_known_host_key", sa.Text(), nullable=True),
            sa.Column("category", sa.String(length=100), nullable=True),
            sa.Column("tags", sa.JSON(), nullable=True),
            sa.Column("is_healthy", sa.Boolean(), nullable=True, server_default="true"),
            sa.Column("last_health_check", sa.DateTime(timezone=True), nullable=True),
            sa.Column("health_check_error", sa.Text(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=True, server_default="true"),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=True,
            ),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        insp = inspect(bind)

    if "database_connections" in insp.get_table_names(schema="public") and not any(
        i.get("name") == op.f("ix_database_connections_id")
        for i in insp.get_indexes("database_connections", schema="public")
    ):
        op.create_index(
            op.f("ix_database_connections_id"),
            "database_connections",
            ["id"],
            unique=False,
        )

    if "data_access_rules" not in insp.get_table_names(schema="public"):
        op.create_table(
            "data_access_rules",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("connection_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("target_column", sa.String(length=255), nullable=False),
            sa.Column("apply_to_tables", sa.JSON(), nullable=True),
            sa.Column("external_api_url", sa.Text(), nullable=False),
            sa.Column("external_api_method", sa.String(length=10), nullable=True),
            sa.Column("external_api_headers", sa.JSON(), nullable=True),
            sa.Column("external_api_body", sa.JSON(), nullable=True),
            sa.Column("response_values_path", sa.String(length=500), nullable=False),
            sa.Column("cache_ttl_seconds", sa.Integer(), nullable=True),
            sa.Column("applies_to_roles", sa.JSON(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=True, server_default="true"),
            sa.Column("priority", sa.Integer(), nullable=True, server_default="0"),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=True,
            ),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(
                ["connection_id"],
                ["database_connections.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        insp = inspect(bind)

    if "data_access_rules" in insp.get_table_names(schema="public") and not any(
        i.get("name") == op.f("ix_data_access_rules_id")
        for i in insp.get_indexes("data_access_rules", schema="public")
    ):
        op.create_index(
            op.f("ix_data_access_rules_id"), "data_access_rules", ["id"], unique=False
        )
    if "data_access_rules" in insp.get_table_names(schema="public") and not any(
        i.get("name") == op.f("ix_data_access_rules_connection_id")
        for i in insp.get_indexes("data_access_rules", schema="public")
    ):
        op.create_index(
            op.f("ix_data_access_rules_connection_id"),
            "data_access_rules",
            ["connection_id"],
            unique=False,
        )


def downgrade() -> None:
    op.drop_index(op.f("ix_data_access_rules_connection_id"), table_name="data_access_rules")
    op.drop_index(op.f("ix_data_access_rules_id"), table_name="data_access_rules")
    op.drop_table("data_access_rules")
    op.drop_index(op.f("ix_database_connections_id"), table_name="database_connections")
    op.drop_table("database_connections")
