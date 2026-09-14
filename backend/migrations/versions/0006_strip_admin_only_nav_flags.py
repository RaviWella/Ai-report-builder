"""Strip Config / AI Settings from tenant nav_sections grants.

Those tools move to the admin Observations console and are no longer
grantable per domain.

Idempotent across multi-tenant migration passes.

Revision ID: 0006_strip_admin_only_nav_flags
Revises: 0005_nav_sections_boolean_map
Create Date: 2026-09-02
"""

from __future__ import annotations

import json

from alembic import op
import sqlalchemy as sa

revision = "0006_strip_admin_only_nav_flags"
down_revision = "0005_nav_sections_boolean_map"
branch_labels = None
depends_on = None

_ADMIN_ONLY = ("Config", "AI Settings")

_DEFAULT = {
    "Chat": False,
    "Builder": False,
    "Documents": True,
    "Viewer": True,
    "How it works": False,
}


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


def _clean(raw) -> dict[str, bool]:  # noqa: ANN001
    if raw is None:
        return dict(_DEFAULT)
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return dict(_DEFAULT)
    if not isinstance(raw, dict):
        return dict(_DEFAULT)
    if "sections" in raw and isinstance(raw.get("sections"), list):
        enabled = {str(x) for x in raw["sections"]}
        return {key: key in enabled for key in _DEFAULT}
    flags = dict(_DEFAULT)
    for key in _DEFAULT:
        if key not in raw:
            continue
        value = raw[key]
        if isinstance(value, bool):
            flags[key] = value
        elif isinstance(value, (int, float)) and value in (0, 1):
            flags[key] = bool(value)
    return flags


def upgrade() -> None:
    if not _column_exists():
        return

    bind = op.get_bind()
    op.execute(
        sa.text(
            f"""
            ALTER TABLE platform.tenant_provision_status
            ALTER COLUMN nav_sections
            SET DEFAULT '{json.dumps(_DEFAULT)}'::jsonb
            """
        )
    )
    rows = bind.execute(
        sa.text("SELECT subdomain, nav_sections FROM platform.tenant_provision_status")
    ).fetchall()
    for subdomain, nav_sections in rows:
        flags = _clean(nav_sections)
        for key in _ADMIN_ONLY:
            flags.pop(key, None)
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


def downgrade() -> None:
    if not _column_exists():
        return
    # Re-introduce admin-only keys as false (does not restore prior values).
    legacy_default = {
        **_DEFAULT,
        "Config": False,
        "AI Settings": False,
    }
    bind = op.get_bind()
    op.execute(
        sa.text(
            f"""
            ALTER TABLE platform.tenant_provision_status
            ALTER COLUMN nav_sections
            SET DEFAULT '{json.dumps(legacy_default)}'::jsonb
            """
        )
    )
    rows = bind.execute(
        sa.text("SELECT subdomain, nav_sections FROM platform.tenant_provision_status")
    ).fetchall()
    for subdomain, nav_sections in rows:
        flags = _clean(nav_sections)
        flags["Config"] = False
        flags["AI Settings"] = False
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
