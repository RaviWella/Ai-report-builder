"""platform.tenant_provision_status: add nav_sections JSONB

Alters the existing platform.tenant_provision_status table (not a new table).

Stores per-tenant Report Builder sidebar flags as a full boolean map, e.g.
  {"Chat": false, "Builder": false, "Documents": true, "Viewer": true,
   "Config": false, "AI Settings": false, "How it works": false}

By default Documents + Viewer are true; other gated sections are false.
Templates is always visible in the UI and is not stored in this map.

Idempotent: multi-tenant env.py re-runs every revision once per tenant
schema; platform DDL must no-op after the first (public) pass.

Revision ID: 0004_tenant_nav_sections
Revises: 0003_ai_sessions_source_sql
Create Date: 2026-09-02
"""

from alembic import op
import sqlalchemy as sa

revision = "0004_tenant_nav_sections"
down_revision = "0003_ai_sessions_source_sql"
branch_labels = None
depends_on = None

_DEFAULT_NAV_SECTIONS = (
    '{"Chat": false, "Builder": false, "Documents": true, "Viewer": true, '
    '"Config": false, "AI Settings": false, "How it works": false}'
)


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
    # Shared platform table — only add once across public + per-tenant passes.
    if not _column_exists():
        op.execute(
            sa.text(
                f"""
                ALTER TABLE platform.tenant_provision_status
                ADD COLUMN nav_sections JSONB
                DEFAULT '{_DEFAULT_NAV_SECTIONS}'::jsonb
                """
            )
        )

    # Safe on every tenant pass: fill any rows still missing a value.
    op.execute(
        sa.text(
            f"""
            UPDATE platform.tenant_provision_status
            SET nav_sections = '{_DEFAULT_NAV_SECTIONS}'::jsonb
            WHERE nav_sections IS NULL
            """
        )
    )


def downgrade() -> None:
    if _column_exists():
        op.execute(
            sa.text(
                "ALTER TABLE platform.tenant_provision_status DROP COLUMN nav_sections"
            )
        )
