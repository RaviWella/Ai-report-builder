"""Bridge revision for DBs stamped as 0010_datamart_tenant_id (legacy id).

Some environments recorded this revision id before it was renamed to
0010_dm_msg_validation. This no-op node restores a consistent Alembic graph.

Revision ID: 0010_datamart_tenant_id
Revises: 0009_datamart_tenant_id
Create Date: 2026-06-04
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0010_datamart_tenant_id"
down_revision: Union[str, None] = "0009_datamart_tenant_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
