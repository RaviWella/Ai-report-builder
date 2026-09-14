"""Repair platform tables skipped when alembic_version was stamped without upgrade.

Creates public.database_connections, public.data_access_rules, and
hrm_control.tenant_etl_sources when missing (common after DB migration).

Revision ID: 0006
Revises: 0005
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(insp, schema: str | None, name: str) -> bool:
    return name in insp.get_table_names(schema=schema)


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)

    if not _has_table(insp, "public", "database_connections"):
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
        op.create_index(
            op.f("ix_database_connections_id"),
            "database_connections",
            ["id"],
            unique=False,
        )

    if not _has_table(insp, "public", "data_access_rules"):
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
        op.create_index(
            op.f("ix_data_access_rules_id"), "data_access_rules", ["id"], unique=False
        )
        op.create_index(
            op.f("ix_data_access_rules_connection_id"),
            "data_access_rules",
            ["connection_id"],
            unique=False,
        )

    insp = inspect(bind)
    if _has_table(insp, "hrm_control", "tenant_registry"):
        reg_cols = {
            c["name"] for c in insp.get_columns("tenant_registry", schema="hrm_control")
        }
        if "source_connection_id" not in reg_cols:
            op.add_column(
                "tenant_registry",
                sa.Column("source_connection_id", sa.Integer(), nullable=True),
                schema="hrm_control",
            )

    if not _has_table(insp, "hrm_control", "tenant_etl_sources"):
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
            schema="hrm_control",
        )
        op.create_index(
            "ix_tenant_etl_sources_tenant_id",
            "tenant_etl_sources",
            ["tenant_id"],
            unique=False,
            schema="hrm_control",
        )


def downgrade() -> None:
    pass
