"""Merge warehouse repair branch (0005–0007) with datamart branch (dm_public_consolidate_001).

Revision ID: 0008
Revises: dm_public_consolidate_001, 0007
Create Date: 2026-05-21

Both branches fork from 0004. ``alembic upgrade head`` fails until this merge exists.
No DDL — reconciliation migrations already ran on each branch.
"""
from __future__ import annotations

from typing import Sequence, Union

revision: str = "0008"
down_revision: Union[str, tuple[str, ...], None] = ("dm_public_consolidate_001", "0007")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
