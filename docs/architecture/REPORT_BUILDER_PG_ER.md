# Report Builder PostgreSQL ER (schema-per-tenant)

See [SCHEMA_PER_TENANT_MIGRATION_PLAN.md](../SCHEMA_PER_TENANT_MIGRATION_PLAN.md) for the full architecture, ER diagrams, and migration plan.

## Summary

| Schema | Purpose |
|---|---|
| `public` | Alembic template DDL — cloned into each tenant schema |
| `platform` | `tenant_provision_status`, `ai_provider_configs_system` |
| `{tenant}` | All app tables (reports, semantic layer, audit, AI sessions, …) |

Tenant isolation is enforced via `SET search_path TO "{tenant}", public` on every request. The external datamart remains **DB-per-tenant** on the warehouse server (`mint_{datamart_key}`).

## Key tables (per tenant schema)

- `semantic_models` — versioned catalogue (JSONB)
- `report_templates` / `report_template_versions` — report definitions
- `ai_sessions`, `learned_intent`, `learned_column_mapping` — AI / learning
- `audit_log`, `report_runs` — lineage and audit
- `semantic_metrics`, `semantic_glossary` — governed extras

## Platform schema

- `platform.tenant_provision_status` — subdomain, pg_schema, datamart_key, status
- `platform.ai_provider_configs_system` — platform-default AI config

## Operations

```bash
# Greenfield empty DB — single baseline migration (public template + platform)
cd backend && alembic upgrade head

# Onboard a tenant via API (creates schema from public template)
curl -X POST http://localhost:8000/api/v1/platform/internal/tenants/demo_tenant/provision \
  -H 'Content-Type: application/json' \
  -d '{"datamart_key":"demo_tenant"}'
```

**Manual SQL** (register tenant, create schema, retrieve/export all data):

[backend/scripts/sql/schema_per_tenant_manual.sql](../../backend/scripts/sql/schema_per_tenant_manual.sql)

Run in psql/pgAdmin. Replace `demo_tenant` with your tenant schema name throughout.
