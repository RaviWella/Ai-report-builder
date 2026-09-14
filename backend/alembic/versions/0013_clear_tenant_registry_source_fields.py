"""Clear legacy source credentials from tenant_registry (management DB only).

Revision ID: 0013_clear_registry_sources
Revises: 0012_tenant_source_credentials
Create Date: 2026-06-04

Customer source DBs live in tenant_etl_sources. Registry keeps identity + warehouse only.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "0013_clear_registry_sources"
down_revision: Union[str, None] = "0012_tenant_source_credentials"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "hrm_control"


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)

    if "tenant_registry" not in insp.get_table_names(schema=_SCHEMA):
        return

    reg_cols = {c["name"]: c for c in insp.get_columns("tenant_registry", schema=_SCHEMA)}
    for col_name, col_type in (
        ("mysql_host", sa.String(length=255)),
        ("mysql_db", sa.String(length=255)),
        ("mysql_user", sa.String(length=255)),
        ("mysql_password_enc", sa.Text()),
        ("mysql_port", sa.Integer()),
    ):
        if col_name in reg_cols and reg_cols[col_name].get("nullable") is False:
            op.alter_column(
                "tenant_registry",
                col_name,
                existing_type=col_type,
                nullable=True,
                schema=_SCHEMA,
            )

    op.execute(
        sa.text(
            f"""
            UPDATE {_SCHEMA}.tenant_registry
            SET mysql_host = NULL,
                mysql_port = NULL,
                mysql_db = NULL,
                mysql_user = NULL,
                mysql_password_enc = NULL,
                source_connection_id = NULL
            WHERE mysql_host IS NOT NULL
               OR mysql_db IS NOT NULL
               OR mysql_user IS NOT NULL
               OR mysql_password_enc IS NOT NULL
               OR source_connection_id IS NOT NULL
            """
        )
    )


def downgrade() -> None:
    pass
