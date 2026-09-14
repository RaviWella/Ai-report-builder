"""Add template_session_id to datamart_templates

Revision ID: add_template_session_id_001
Revises: add_datamart_workspace_001
Create Date: 2026-05-14

Adds a nullable template_session_id FK on datamart_templates that links to a
hidden datamart_chat_sessions row used for the template's own modify-chat history.
The session is created lazily on first modify-chat message and is NOT shown in
the chat sidebar (its is_active flag is set to False so list_sessions skips it).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID


revision: str = "add_template_session_id_001"
down_revision: Union[str, None] = "add_datamart_workspace_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "datamart_templates",
        sa.Column("template_session_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_dt_template_session_id",
        "datamart_templates",
        "datamart_chat_sessions",
        ["template_session_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_dt_template_session_id",
        "datamart_templates",
        ["template_session_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_dt_template_session_id", "datamart_templates")
    op.drop_constraint("fk_dt_template_session_id", "datamart_templates", type_="foreignkey")
    op.drop_column("datamart_templates", "template_session_id")
