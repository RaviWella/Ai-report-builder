"""Consolidate datamart chat/workspace tables into public schema only.

Revision ID: dm_public_consolidate_001
Revises: tpl_version_report_meta_001
Create Date: 2026-05-19

1. Copy any rows from non-public schemas that still have datamart_* tables.
2. Drop datamart_* copies from those schemas (public retains canonical tables).

Datamart API routes use get_db() (public) — no per-tenant schema copies after this migration.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "dm_public_consolidate_001"
down_revision: Union[str, None] = "tpl_version_report_meta_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# FK-safe insert order; reverse for drops.
_DATAMART_TABLES = (
    "datamart_session_groups",
    "datamart_template_groups",
    "datamart_chat_sessions",
    "datamart_chat_messages",
    "datamart_chat_summaries",
    "datamart_templates",
    "datamart_template_versions",
)

_COPY_FROM_TENANT_MARTS = """
DO $body$
DECLARE
  tenant_schema text;
  tbl text;
  col_list text;
BEGIN
  FOREACH tbl IN ARRAY ARRAY[
    'datamart_session_groups',
    'datamart_template_groups',
    'datamart_chat_sessions',
    'datamart_chat_messages',
    'datamart_chat_summaries',
    'datamart_templates',
    'datamart_template_versions'
  ]
  LOOP
    FOR tenant_schema IN
      SELECT DISTINCT table_schema
      FROM information_schema.tables
      WHERE table_name = 'datamart_session_groups'
        AND table_schema NOT IN (
          'public', 'information_schema', 'pg_catalog', 'pg_toast'
        )
    LOOP
      IF NOT EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = tenant_schema
          AND table_name = tbl
      ) THEN
        CONTINUE;
      END IF;

      SELECT string_agg(format('%I', column_name), ', ' ORDER BY ordinal_position)
      INTO col_list
      FROM information_schema.columns c
      WHERE c.table_schema = 'public'
        AND c.table_name = tbl
        AND EXISTS (
          SELECT 1
          FROM information_schema.columns c2
          WHERE c2.table_schema = tenant_schema
            AND c2.table_name = tbl
            AND c2.column_name = c.column_name
        );

      IF col_list IS NULL OR col_list = '' THEN
        CONTINUE;
      END IF;

      EXECUTE format(
        'INSERT INTO public.%I (%s) SELECT %s FROM %I.%I ON CONFLICT (id) DO NOTHING',
        tbl,
        col_list,
        col_list,
        tenant_schema,
        tbl
      );
    END LOOP;
  END LOOP;
END $body$;
"""

_DROP_FROM_TENANT_MARTS = """
DO $body$
DECLARE
  tenant_schema text;
  tbl text;
BEGIN
  FOR tenant_schema IN
    SELECT DISTINCT table_schema
    FROM information_schema.tables
    WHERE table_name = 'datamart_session_groups'
      AND table_schema NOT IN (
        'public', 'information_schema', 'pg_catalog', 'pg_toast'
      )
  LOOP
    FOREACH tbl IN ARRAY ARRAY[
      'datamart_template_versions',
      'datamart_templates',
      'datamart_chat_summaries',
      'datamart_chat_messages',
      'datamart_chat_sessions',
      'datamart_template_groups',
      'datamart_session_groups'
    ]
    LOOP
      IF EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = tenant_schema
          AND table_name = tbl
      ) THEN
        EXECUTE format('DROP TABLE IF EXISTS %I.%I CASCADE', tenant_schema, tbl);
      END IF;
    END LOOP;
  END LOOP;
END $body$;
"""


def upgrade() -> None:
    op.execute(_COPY_FROM_TENANT_MARTS)
    op.execute(_DROP_FROM_TENANT_MARTS)


def downgrade() -> None:
    # Data copied into public is not moved back to tenant schemas.
    pass
