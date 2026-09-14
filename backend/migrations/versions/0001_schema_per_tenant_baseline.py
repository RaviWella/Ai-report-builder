"""Greenfield schema-per-tenant baseline (empty DB).

Creates:
  - platform schema (tenant_provision_status, ai_provider_configs_system)
  - public template DDL for all tenant-scoped tables (no tenant_id, no tenants/users)

Revision ID: 0001_schema_per_tenant_baseline
Revises:
Create Date: 2026-08-24
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0001_schema_per_tenant_baseline"
down_revision = None
branch_labels = None
depends_on = None


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

    op.create_table(
        "semantic_models",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("catalog", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("version", name="uq_semantic_version"),
    )

    op.create_table(
        "report_templates",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("module", sa.String(64), server_default="General", nullable=False),
        sa.Column("status", sa.String(16), server_default="draft", nullable=False),
        sa.Column("current_published_version_id", sa.String(64), nullable=True),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_report_templates_module", "report_templates", ["module"])
    op.create_index("ix_report_templates_status", "report_templates", ["status"])

    op.create_table(
        "report_template_versions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("template_id", sa.String(64), sa.ForeignKey("report_templates.id"), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("data_spec", JSONB(), nullable=False),
        sa.Column("presentation_spec", JSONB(), nullable=False),
        sa.Column("semantic_version_ref", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), server_default="draft", nullable=False),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("template_id", "version_no", name="uq_template_version_no"),
    )
    op.create_index("ix_report_template_versions_template_id", "report_template_versions", ["template_id"])

    op.create_table(
        "template_uploads",
        sa.Column("template_id", sa.String(64), sa.ForeignKey("report_templates.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(128), server_default="application/octet-stream", nullable=False),
        sa.Column("content_enc", sa.LargeBinary(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "document_categories",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("doc_type", sa.String(16), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("doc_type", "name", name="uq_doc_category"),
    )
    op.create_index("ix_document_categories_doc_type", "document_categories", ["doc_type"])

    op.create_table(
        "letterheads",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("logo_data_url", sa.Text(), nullable=True),
        sa.Column("header_html", sa.Text(), nullable=True),
        sa.Column("footer_html", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("name", name="uq_letterhead_name"),
    )

    op.create_table(
        "manual_fields",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("key", sa.String(80), nullable=False),
        sa.Column("label", sa.String(160), nullable=False),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("key", name="uq_manual_field_key"),
    )

    op.create_table(
        "report_schedules",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("template_id", sa.String(64), sa.ForeignKey("report_templates.id"), nullable=False),
        sa.Column("cron", sa.String(120), nullable=False),
        sa.Column("recipients", JSONB(), server_default="[]"),
        sa.Column("format", sa.String(8), server_default="pdf"),
        sa.Column("runtime_params", JSONB(), server_default="{}"),
        sa.Column("enabled", sa.Boolean(), server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_report_schedules_template_id", "report_schedules", ["template_id"])

    op.create_table(
        "ai_sessions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("template_id", sa.String(64), nullable=True),
        sa.Column("title", sa.String(160), nullable=True),
        sa.Column("messages", JSONB(), server_default="[]"),
        sa.Column("working_data_spec", JSONB(), nullable=True),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_ai_sessions_template_id", "ai_sessions", ["template_id"])

    op.create_table(
        "ai_provider_configs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("provider", sa.String(32), server_default="anthropic", nullable=False),
        sa.Column("model", sa.String(128), server_default="claude-opus-4-8", nullable=False),
        sa.Column("base_url", sa.String(255), nullable=True),
        sa.Column("api_key_encrypted", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("updated_by", sa.String(64), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "audit_log",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("target_type", sa.String(64), nullable=True),
        sa.Column("target_id", sa.String(64), nullable=True),
        sa.Column("detail", JSONB(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_audit_log_created_at", "audit_log", ["created_at"])

    op.create_table(
        "sql_cache",
        sa.Column("version_id", sa.String(64), primary_key=True),
        sa.Column("sql_text", sa.Text(), nullable=False),
        sa.Column("semantic_version_ref", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "report_runs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("report_id", sa.String(64), nullable=True),
        sa.Column("semantic_version_ref", sa.Integer(), nullable=True),
        sa.Column("compiled_sql_hash", sa.String(64), nullable=True),
        sa.Column("result_checksum", sa.String(64), nullable=True),
        sa.Column("datamart_snapshot_ref", sa.String(128), nullable=True),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(16), server_default="ok", nullable=False),
        sa.Column("fmt", sa.String(16), nullable=True),
        sa.Column("executed_by", sa.String(64), nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_report_runs_report_id", "report_runs", ["report_id"])
    op.create_index("ix_report_runs_executed_at", "report_runs", ["executed_at"])

    op.create_table(
        "mart_validation_result",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("validation_run_id", sa.String(64), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("category", sa.String(24), nullable=False),
        sa.Column("severity", sa.String(12), nullable=False),
        sa.Column("status", sa.String(8), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("details", JSONB(), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_mvr_run_id", "mart_validation_result", ["validation_run_id"])
    op.create_index("ix_mvr_name", "mart_validation_result", ["name"])
    op.create_index("ix_mvr_created_at", "mart_validation_result", ["created_at"])

    op.create_table(
        "semantic_metrics",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("key", sa.String(80), nullable=False),
        sa.Column("definition", JSONB(), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_semantic_metrics_key", "semantic_metrics", ["key"])

    op.create_table(
        "semantic_glossary",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("term_key", sa.String(120), nullable=False),
        sa.Column("definition", JSONB(), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_semantic_glossary_term_key", "semantic_glossary", ["term_key"])

    op.create_table(
        "learned_intent",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("phrase_key", sa.String(255), nullable=False),
        sa.Column("phrase_sample", sa.Text(), nullable=False),
        sa.Column("spec", JSONB(), nullable=False),
        sa.Column("signature", sa.String(64), nullable=False),
        sa.Column("source", sa.String(16), server_default="deterministic", nullable=False),
        sa.Column("certified", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("hits", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_used_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("phrase_key", name="uq_learned_intent_phrase"),
    )
    op.create_index("ix_learned_intent_phrase_key", "learned_intent", ["phrase_key"])
    op.create_index("ix_learned_intent_signature", "learned_intent", ["signature"])

    op.create_table(
        "learned_column_mapping",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("header_key", sa.String(255), nullable=False),
        sa.Column("header_sample", sa.String(255), nullable=False),
        sa.Column("ref", sa.String(255), nullable=True),
        sa.Column("hits", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_used_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("header_key", name="uq_learned_col_header"),
    )
    op.create_index("ix_learned_column_mapping_header_key", "learned_column_mapping", ["header_key"])

    op.create_table(
        "field_request",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("header_key", sa.String(255), nullable=False),
        sa.Column("header_sample", sa.String(255), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("status", sa.String(16), server_default="open", nullable=False),
        sa.Column("hits", sa.Integer(), server_default="1", nullable=False),
        sa.Column("requested_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_requested_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("header_key", name="uq_field_request_header"),
    )
    op.create_index("ix_field_request_header_key", "field_request", ["header_key"])


def downgrade() -> None:
    for table in (
        "field_request",
        "learned_column_mapping",
        "learned_intent",
        "semantic_glossary",
        "semantic_metrics",
        "mart_validation_result",
        "report_runs",
        "sql_cache",
        "audit_log",
        "ai_provider_configs",
        "ai_sessions",
        "report_schedules",
        "manual_fields",
        "letterheads",
        "document_categories",
        "template_uploads",
        "report_template_versions",
        "report_templates",
        "semantic_models",
    ):
        op.drop_table(table)

    op.drop_table("ai_provider_configs_system", schema="platform")
    op.drop_table("tenant_provision_status", schema="platform")
    op.execute("DROP SCHEMA IF EXISTS platform CASCADE")
