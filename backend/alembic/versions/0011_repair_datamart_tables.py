"""Create missing public datamart_* tables when alembic_version is ahead of actual DDL.

Revision ID: 0011_repair_datamart_tables
Revises: 0010_dm_msg_validation
Create Date: 2026-05-27

Safe to re-run: uses SQLAlchemy create_all(..., checkfirst=True) only for tables
that are absent from public schema. Runs after tenant_id + validation migrations so
create_all matches the final model shape.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect

revision: str = "0011_repair_datamart_tables"
down_revision: Union[str, None] = "0010_dm_msg_validation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DATAMART_TABLES = (
    "datamart_session_groups",
    "datamart_template_groups",
    "datamart_chat_sessions",
    "datamart_chat_messages",
    "datamart_chat_summaries",
    "datamart_templates",
    "datamart_template_versions",
)


def _missing_tables(bind) -> list[str]:
    insp = inspect(bind)
    return [name for name in _DATAMART_TABLES if not insp.has_table(name, schema="public")]


def upgrade() -> None:
    bind = op.get_bind()
    missing = _missing_tables(bind)
    if not missing:
        return

    import app.models.datamart_chat  # noqa: F401
    import app.models.datamart_workspace  # noqa: F401
    from app.core.database import Base

    tables = [
        Base.metadata.tables[name]
        for name in _DATAMART_TABLES
        if name in Base.metadata.tables and name in missing
    ]
    if not tables:
        return

    Base.metadata.create_all(bind, tables=tables, checkfirst=True)


def downgrade() -> None:
    pass
