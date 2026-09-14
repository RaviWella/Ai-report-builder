"""schema-per-tenant baseline: platform control plane + drop tenant_id columns

Revision ID: 0017_schema_per_tenant
Revises: 0016_manual_fields
Create Date: 2026-08-24
"""

from alembic import op
import sqlalchemy as sa

revision = "0017_schema_per_tenant"
down_revision = "0016_manual_fields"
branch_labels = None
depends_on = None


def _drop_tenant_id(table: str) -> None:
    op.execute(f'ALTER TABLE "{table}" DROP COLUMN IF EXISTS tenant_id CASCADE')


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS platform")

    op.create_table(
        "tenant_provision_status",
        sa.Column("subdomain", sa.String(255), primary_key=True),
        sa.Column("pg_schema", sa.String(63), nullable=False),
        sa.Column("datamart_key", sa.String(128), nullable=False),
        sa.Column("status", sa.String(32), server_default="active", nullable=False),
        sa.Column("provisioned_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("provisioned_by", sa.String(255), nullable=True),
        schema="platform",
    )

    op.create_table(
        "ai_provider_configs_system",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("provider", sa.String(32), server_default="anthropic"),
        sa.Column("model", sa.String(128), server_default="claude-opus-4-8"),
        sa.Column("base_url", sa.String(255), nullable=True),
        sa.Column("api_key_encrypted", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), server_default=sa.true()),
        sa.Column("updated_by", sa.String(64), server_default="system"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="platform",
    )

    # Migrate tenants registry → platform.tenant_provision_status
    op.execute("""
        INSERT INTO platform.tenant_provision_status (subdomain, pg_schema, datamart_key, status, provisioned_by)
        SELECT
            id,
            REPLACE(REPLACE(LOWER(id), '-', '_'), '.', '_'),
            datamart_key,
            status,
            'migration_0017'
        FROM tenants
        ON CONFLICT (subdomain) DO NOTHING
    """)

    # Migrate __system__ AI config to platform
    op.execute("""
        INSERT INTO platform.ai_provider_configs_system (id, provider, model, base_url, api_key_encrypted, enabled, updated_by)
        SELECT id, provider, model, base_url, api_key_encrypted, enabled, updated_by
        FROM ai_provider_configs
        WHERE tenant_id = '__system__'
        ON CONFLICT (id) DO NOTHING
    """)

    # Drop old unique constraints that include tenant_id
    for stmt in (
        'ALTER TABLE semantic_models DROP CONSTRAINT IF EXISTS uq_semantic_tenant_version',
        'ALTER TABLE document_categories DROP CONSTRAINT IF EXISTS uq_doc_category',
        'ALTER TABLE letterheads DROP CONSTRAINT IF EXISTS uq_letterhead_name',
        'ALTER TABLE manual_fields DROP CONSTRAINT IF EXISTS uq_manual_field_key',
        'ALTER TABLE learned_intent DROP CONSTRAINT IF EXISTS uq_learned_intent_phrase',
        'ALTER TABLE learned_column_mapping DROP CONSTRAINT IF EXISTS uq_learned_col_header',
        'ALTER TABLE field_request DROP CONSTRAINT IF EXISTS uq_field_request_header',
        'ALTER TABLE ai_provider_configs DROP CONSTRAINT IF EXISTS ai_provider_configs_tenant_id_key',
    ):
        op.execute(stmt)

    # Drop tenant_id from tenant-scoped tables
    for table in (
        "semantic_models",
        "report_templates",
        "template_uploads",
        "document_categories",
        "letterheads",
        "manual_fields",
        "ai_sessions",
        "ai_provider_configs",
        "audit_log",
        "report_runs",
        "mart_validation_result",
        "semantic_metrics",
        "semantic_glossary",
        "learned_intent",
        "learned_column_mapping",
        "field_request",
    ):
        _drop_tenant_id(table)

    op.drop_table("users")
    op.drop_table("tenants")

    # New unique constraints (schema provides tenant isolation)
    op.create_unique_constraint("uq_semantic_version", "semantic_models", ["version"])
    op.create_unique_constraint("uq_doc_category", "document_categories", ["doc_type", "name"])
    op.create_unique_constraint("uq_letterhead_name", "letterheads", ["name"])
    op.create_unique_constraint("uq_manual_field_key", "manual_fields", ["key"])
    op.create_unique_constraint("uq_learned_intent_phrase", "learned_intent", ["phrase_key"])
    op.create_unique_constraint("uq_learned_col_header", "learned_column_mapping", ["header_key"])
    op.create_unique_constraint("uq_field_request_header", "field_request", ["header_key"])


def downgrade() -> None:
    raise NotImplementedError("Schema-per-tenant migration is not reversible")
