# Tenant onboarding (standard flow)

## Two tables in the management database (`hrm_control`)

| Table | When populated | Contents |
|-------|----------------|----------|
| **`tenant_registry`** | Customer onboarding (ops / API) | `tenant_id`, `display_name`, `is_active`, **warehouse** routing (`warehouse_db`, `warehouse_host`, …). No customer source DB credentials. |
| **`tenant_etl_sources`** | After login, in **Settings → Source Databases** | Per-tenant source keys, connection host/port/database/user/password (encrypted), `source_schema`, primary flag, extractor profile. |

Both tables live in the **same application database** (e.g. `hrm_platform` / `mint_analytics_*_management_db`). They are not stored in the per-tenant analytics warehouse.

After migration **`0013_clear_registry_sources`**, `tenant_registry` rows should have **NULL** in `mysql_host`, `mysql_db`, `mysql_user`, `mysql_password_enc`, and `source_connection_id`. If you still see values, run:

```bash
cd backend && alembic upgrade head
```

## Step-by-step

### 1. Onboarding — register tenant only

```bash
curl -X POST \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"tenant_id": "etsteasuat", "display_name": "ET STEAS UAT"}' \
  https://<api-host>/api/v1/tenants/provision-minimal
```

Run migration first on the application DB:

```bash
cd backend && alembic upgrade head
```

This creates/updates `tenant_etl_sources` credential columns (`0012_tenant_source_credentials`).

### 2. HRIS launch — user signs in

MinHRM redirects to `/auth?payload=...`. The API checks:

- Payload decrypts with `HRIS_LAUNCH_SECRET_KEY`
- `subdomain` matches a row in `tenant_registry` with `is_active = true`

No source DB is required at this step.

### 3. After login — user adds source databases (UI)

**Settings → Source Databases** calls `POST /api/v1/tenants/etl-sources/`.

Data is stored in **`hrm_control.tenant_etl_sources`** (management DB), keyed by `tenant_id` + `source_key`.

### 4. ETL

ETL reads active rows from `tenant_etl_sources` and connects to customer MySQL/PostgreSQL using those credentials.

## Rules

- One `source_key` per tenant (e.g. `uat_for_amazon`). Duplicates return **400**, not 500.
- Do not put customer source passwords in `tenant_registry`.
- Legacy rows may still use `connection_id` → warehouse `database_connections`; new saves use inline credentials on `tenant_etl_sources` only.

## Optional automation

```env
HRIS_LAUNCH_AUTO_PROVISION_TENANT=true
```

Creates a minimal `tenant_registry` row on first successful HRIS decrypt (off by default in production).
