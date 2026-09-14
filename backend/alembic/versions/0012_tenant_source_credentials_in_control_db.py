"""Store customer source DB credentials on tenant_etl_sources (management DB).

Revision ID: 0012_tenant_source_credentials
Revises: 0011_repair_datamart_tables
Create Date: 2026-06-04

Standard model:
  - hrm_control.tenant_registry: tenant identity + analytics warehouse routing
  - hrm_control.tenant_etl_sources: per-tenant source DB connection details (FK tenant_id)
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "0012_tenant_source_credentials"
down_revision: Union[str, None] = "0011_repair_datamart_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "hrm_control"

_ETL_CREDENTIAL_COLS = (
    ("host", sa.String(length=500)),
    ("port", sa.Integer()),
    ("database_name", sa.String(length=255)),
    ("username", sa.String(length=255)),
    ("password_encrypted", sa.Text()),
)


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)

    if "tenant_etl_sources" in insp.get_table_names(schema=_SCHEMA):
        existing = {
            c["name"]
            for c in insp.get_columns("tenant_etl_sources", schema=_SCHEMA)
        }
        for name, col_type in _ETL_CREDENTIAL_COLS:
            if name not in existing:
                op.add_column(
                    "tenant_etl_sources",
                    sa.Column(name, col_type, nullable=True),
                    schema=_SCHEMA,
                )

    if "tenant_registry" in insp.get_table_names(schema=_SCHEMA):
        reg_cols = {
            c["name"]: c for c in insp.get_columns("tenant_registry", schema=_SCHEMA)
        }
        for col_name in ("mysql_host", "mysql_db", "mysql_user", "mysql_password_enc"):
            if col_name in reg_cols and reg_cols[col_name].get("nullable") is False:
                op.alter_column(
                    "tenant_registry",
                    col_name,
                    existing_type=sa.String(length=255)
                    if col_name != "mysql_password_enc"
                    else sa.Text(),
                    nullable=True,
                    schema=_SCHEMA,
                )


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if "tenant_etl_sources" not in insp.get_table_names(schema=_SCHEMA):
        return
    existing = {
        c["name"] for c in insp.get_columns("tenant_etl_sources", schema=_SCHEMA)
    }
    for name, _ in reversed(_ETL_CREDENTIAL_COLS):
        if name in existing:
            op.drop_column("tenant_etl_sources", name, schema=_SCHEMA)
