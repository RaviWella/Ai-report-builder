"""Convert nav_sections from legacy allow-list to full boolean map.

Legacy:  {"sections": ["Documents", "Viewer"]}
New:     {"Chat": false, "Builder": false, "Documents": true, "Viewer": true,
          "Config": false, "AI Settings": false, "How it works": false}

Idempotent across multi-tenant migration passes.

Revision ID: 0005_nav_sections_boolean_map
Revises: 0004_tenant_nav_sections
Create Date: 2026-09-02
"""

from __future__ import annotations

import json

from alembic import op
import sqlalchemy as sa

revision = "0005_nav_sections_boolean_map"
down_revision = "0004_tenant_nav_sections"
branch_labels = None
depends_on = None

_KEYS = (
    "Chat",
    "Builder",
    "Documents",
    "Viewer",
    "Config",
    "AI Settings",
    "How it works",
)

_DEFAULT = {
    "Chat": False,
    "Builder": False,
    "Documents": True,
    "Viewer": True,
    "Config": False,
    "AI Settings": False,
    "How it works": False,
}


def _to_flags(raw) -> dict[str, bool]:  # noqa: ANN001
    if raw is None:
        return dict(_DEFAULT)
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return dict(_DEFAULT)
    if isinstance(raw, list):
        enabled = {str(x) for x in raw}
        return {key: key in enabled for key in _KEYS}
    if not isinstance(raw, dict):
        return dict(_DEFAULT)
    if "sections" in raw and isinstance(raw.get("sections"), list):
        enabled = {str(x) for x in raw["sections"]}
        return {key: key in enabled for key in _KEYS}
    if any(key in raw for key in _KEYS):
        flags = dict(_DEFAULT)
        for key in _KEYS:
            if key not in raw:
                continue
            value = raw[key]
            if isinstance(value, bool):
                flags[key] = value
            elif isinstance(value, (int, float)) and value in (0, 1):
                flags[key] = bool(value)
        return flags
    return dict(_DEFAULT)


def _column_exists() -> bool:
    bind = op.get_bind()
    return (
        bind.execute(
            sa.text(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'platform'
                  AND table_name = 'tenant_provision_status'
                  AND column_name = 'nav_sections'
                """
            )
        ).scalar()
        is not None
    )


def upgrade() -> None:
    if not _column_exists():
        return

    bind = op.get_bind()
    rows = bind.execute(
        sa.text("SELECT subdomain, nav_sections FROM platform.tenant_provision_status")
    ).fetchall()

    for subdomain, nav_sections in rows:
        flags = _to_flags(nav_sections)
        bind.execute(
            sa.text(
                """
                UPDATE platform.tenant_provision_status
                SET nav_sections = CAST(:flags AS jsonb)
                WHERE subdomain = :subdomain
                """
            ),
            {"flags": json.dumps(flags), "subdomain": subdomain},
        )

    # Keep DB default aligned with the new shape for future inserts.
    op.execute(
        sa.text(
            f"""
            ALTER TABLE platform.tenant_provision_status
            ALTER COLUMN nav_sections
            SET DEFAULT '{json.dumps(_DEFAULT)}'::jsonb
            """
        )
    )


def downgrade() -> None:
    if not _column_exists():
        return

    bind = op.get_bind()
    rows = bind.execute(
        sa.text("SELECT subdomain, nav_sections FROM platform.tenant_provision_status")
    ).fetchall()

    for subdomain, nav_sections in rows:
        flags = _to_flags(nav_sections)
        enabled = [key for key in _KEYS if flags.get(key)]
        legacy = {"sections": enabled}
        bind.execute(
            sa.text(
                """
                UPDATE platform.tenant_provision_status
                SET nav_sections = CAST(:flags AS jsonb)
                WHERE subdomain = :subdomain
                """
            ),
            {"flags": json.dumps(legacy), "subdomain": subdomain},
        )

    op.execute(
        sa.text(
            """
            ALTER TABLE platform.tenant_provision_status
            ALTER COLUMN nav_sections
            SET DEFAULT '{"sections": ["Documents", "Viewer"]}'::jsonb
            """
        )
    )
