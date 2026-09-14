# MintHRM Intelligence Platform — Deployment Guide

> **Version: v1.0.0** — Foundation Release
> **Application DB:** dedicated PostgreSQL database `hrm_platform` (config, tenants, ETL source registry).
> **Warehouse:** one PostgreSQL **database** per customer (`hrm_wh_{tenant_id}`) with schemas `hr_raw`, `hr`, `hr_semantic`, `hr_control`.
> **Source:** PostgreSQL and/or MySQL (customer operational DBs — not stored in the app DB except connection metadata).

### Three database roles

| Role | Database | Typical host | Contents |
|------|----------|--------------|----------|
| **Application** | `hrm_platform` (default) | Control-plane Postgres | `hrm_control.*` — tenants, ETL sources, encrypted connection refs |
| **Warehouse** | `hrm_wh_{tenant_id}` | **Separate** analytics Postgres | Staging, marts, semantic views, per-tenant ETL runs |
| **Source** | Customer DB | Customer network | Upstream HR data (read-only via ETL) |

In **production**, the application DB and warehouse DB should be on **different servers**. Local dev often uses one Postgres instance for both.

---

## Quick Start

### Prerequisites
- Docker + Docker Compose
- Node.js 20+
- Python 3.11+ (Docker image) or **3.13 locally** with `requirements-core.txt` (no AI stack)
- Access to customer source databases (MySQL or PostgreSQL)

### Local backend (Python 3.13, no extra Python install)

The full `backend/requirements.txt` pins LangChain and `numpy==1.26.4`, which does not build on Windows + Python 3.13. For API + ETL only, use the slim lockfile:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements-core.txt
```

Then migrate and run (use `postgresql+psycopg2` or plain `postgresql://` for Alembic):

```powershell
$env:DATABASE_URL = "postgresql+psycopg2://postgres:admin123@localhost:5432/hrm_platform"
$env:APP_DATABASE_NAME = "hrm_platform"
alembic upgrade head
cd ..
python scripts/register_tenant.py
cd backend
uvicorn app.main:app --reload --port 8000
```

HR metrics, ETL, and tenant APIs work without LangChain. `/experience/ask` uses regex routing only unless you add AI packages later.

### 1. Configure environment

```bash
cp .env.docker .env.docker.local
# Edit .env.docker.local — set API_KEY, DB_ENCRYPTION_KEY
```

### 2. Start containers

```bash
docker compose up -d --build
```

### 3. Run database migrations

**Docker / Jenkins:** `docker-entrypoint.sh` runs `alembic upgrade head` once before uvicorn (`RUN_MIGRATIONS_IN_ENTRYPOINT=true` by default). Set `RUN_MIGRATIONS_ON_STARTUP=false` so the API lifespan does not migrate again.

**Local uvicorn (no Docker):** enable lifespan migrations or run Alembic manually:

```bash
cd backend
# Create hrm_platform once (Docker: init-db.sh; production: DBA). Then migrate:
export DATABASE_URL=postgresql://postgres:password@localhost:5432/hrm_platform
export APP_AUTO_PROVISION=false
alembic upgrade head
# Or: RUN_MIGRATIONS_ON_STARTUP=true when starting uvicorn
```

Run Alembic against the **application** database (`hrm_platform`), not the generic `postgres` database.

**Provisioning policy (default):**

| Database | Auto-create? | Env |
|----------|----------------|-----|
| `hrm_platform` (application) | **No** — DBA / `init-db.sh` / manual `CREATE DATABASE` | `APP_AUTO_PROVISION=false` |
| `hrm_wh_{tenant_id}` (warehouse) | **Yes** — on first ETL or tenant register | `WAREHOUSE_AUTO_PROVISION=true` |

Set `APP_AUTO_PROVISION=true` only for local convenience when nothing has created `hrm_platform` yet.

#### Migrate from legacy `postgres` database

If Alembic and tenants were created on the default `postgres` database, copy control-plane data into `hrm_platform`:

```powershell
cd e:\mint-analytics\mint-hrm
python scripts/migrate_app_db_to_hrm_platform.py --dry-run
python scripts/migrate_app_db_to_hrm_platform.py
```

| Flag | Purpose |
|------|---------|
| `--source-db postgres` | Legacy database (default) |
| `--target-db hrm_platform` | Application database (default: `APP_DATABASE_NAME`) |
| `--dry-run` | Preview only |
| `--replace` | Truncate target `hrm_control` tables before copy |
| `--skip-alembic` | Skip `alembic upgrade head` on the target |

Then set `DATABASE_URL=.../hrm_platform` in `backend/.env` and restart the API.

Optional env (backend):

```env
APP_AUTO_PROVISION=false
RUN_MIGRATIONS_IN_ENTRYPOINT=true
RUN_MIGRATIONS_ON_STARTUP=false
MIGRATION_FAIL_FAST=true
WAREHOUSE_DEFAULT_ISOLATION=database
WAREHOUSE_DB_PREFIX=hrm_wh_
WAREHOUSE_AUTO_PROVISION=true
```

Set `WAREHOUSE_DEFAULT_ISOLATION=schema` to revert to legacy `{tenant_id}_hr*` schemas on the platform DB only.

### Production — application DB and warehouse on separate servers

**Provisioning:** do **not** auto-create the application database (`APP_AUTO_PROVISION=false`).  
Only auto-create **per-tenant warehouse** databases when needed (`WAREHOUSE_AUTO_PROVISION=true`).

1. **Application server** — DBA creates `hrm_platform`. On deploy, the backend container entrypoint runs `alembic upgrade head` once (`RUN_MIGRATIONS_IN_ENTRYPOINT=true`, `RUN_MIGRATIONS_ON_STARTUP=false`).  
   `APPLICATION_DATABASE_URL` is the app runtime connection only (Alembic, `/health`, and all API routes use the same **psycopg2** sync driver).  
   `POSTGRES_ADMIN_URL` is **not** required unless you set `APP_AUTO_PROVISION=true`.

   Use the `postgresql+psycopg2` driver and include SSL query params when the server requires TLS:

```env
APPLICATION_DATABASE_URL=postgresql+psycopg2://hrm_app:SECRET@app-pg.prod:5432/hrm_platform?sslmode=require
```

   Do **not** use `postgresql+asyncpg` — it is not supported and rejects `sslmode`. Legacy `+asyncpg` URLs in env are normalized to `+psycopg2` at runtime, but production configs should set `+psycopg2` explicitly.

   **Post-deploy checklist (application DB + SSL):**

   1. Confirm `GET /health` returns healthy.
   2. Confirm `GET /api/v1/tenants/etl-sources/` returns 200 (not 500 from driver/ssl errors).
   3. Provision tenant warehouse DB if missing (`hrm_wh_{tenant_id}`) before first ETL.
   4. Create an ETL source and run a test ETL job.

2. **Warehouse server** — set global defaults in `backend/.env`:

```env
WAREHOUSE_ADMIN_URL=postgresql://admin:SECRET@warehouse-pg.prod:5432/postgres
WAREHOUSE_DEFAULT_HOST=warehouse-pg.prod
WAREHOUSE_DEFAULT_PORT=5432
WAREHOUSE_DEFAULT_USER=hrm_warehouse_app
WAREHOUSE_DEFAULT_PASSWORD=SECRET
WAREHOUSE_AUTO_PROVISION=true
```

3. **Per-tenant override** (optional) — columns on `hrm_control.tenant_registry`:

| Column | Purpose |
|--------|---------|
| `warehouse_host` | Analytics Postgres host |
| `warehouse_port` | Port (default 5432) |
| `warehouse_db` | Database name (`hrm_wh_{tenant_id}`) |
| `warehouse_user` / `warehouse_password_enc` | App role on warehouse server (Fernet-encrypted password) |

Example after tenant register (encrypt password with your `DB_ENCRYPTION_KEY`):

```sql
UPDATE hrm_control.tenant_registry
SET warehouse_host = 'warehouse-pg.prod',
    warehouse_port = 5432,
    warehouse_db = 'hrm_wh_acme_corp',
    warehouse_user = 'hrm_wh_acme',
    warehouse_password_enc = '<fernet-ciphertext>'
WHERE tenant_id = 'acme_corp';
```

4. **ETL source credentials** — add in the UI (**Settings → Source Databases**). One save stores encrypted credentials in the tenant warehouse (`database_connections`) and registers `hrm_control.tenant_etl_sources`. The primary source is mirrored into `tenant_registry` for admin listing. Customer **source** DBs are not the analytics warehouse.

5. If DBAs create warehouse databases manually, set `WAREHOUSE_AUTO_PROVISION=false` and create `hrm_wh_{tenant_id}` on the warehouse server before the first ETL run.

Resolution order for warehouse connections: `tenant_registry.warehouse_*` → `WAREHOUSE_DEFAULT_*` env → same host as `APPLICATION_DATABASE_URL` (dev fallback only).

### ETL source scenarios (per tenant)

Register sources under **Settings → ETL Sources** (`/settings/etl-sources`). The pipeline runs **every** active source on each ETL job.

| Scenario | Layout | Example |
|----------|--------|---------|
| **A** | MySQL only | 1× MySQL (`legacy_mysql`), primary |
| **B** | 1 MySQL + 2+ PostgreSQL | 1× MySQL primary + `product_pg`, `billing_pg` |
| **C** | PostgreSQL only (2+) | `core_pg`, `analytics_pg` — no MySQL |

- **Primary** source → writes `stg_*` tables.
- **Other** sources → `stg_*__{source_key}` (dbt can union later).
- PostgreSQL sources need **customer schema** + saved connection credentials.
- Check layout: `GET /api/v1/tenants/etl-sources/scenario`

### 4. Verify

```bash
# Backend health
curl http://localhost:8001/health

# Frontend
open http://localhost:5174

# Ask an HR question
curl -X POST \
  -H "X-API-Key: hrm-api-key-change-in-production" \
  -H "X-Tenant-Id: demo_tenant" \
  -H "Content-Type: application/json" \
  -d '{"question":"How many employees do we have?"}' \
  http://localhost:8001/api/v1/experience/ask
```

---

## Production — split UI and API hosts

When the UI and API use different domains (example):

| Role | Host |
|------|------|
| Frontend | `mint-analytics-new.minchy.ai` |
| Backend | `mint-analytics-new-api.minchy.ai` |

1. **Build the frontend** with the full API URL (baked into JS):

   ```env
   REACT_APP_API_BASE_URL=https://mint-analytics-new-api.minchy.ai/api/v1
   REACT_APP_API_KEY=<same as backend API_KEY>
   ```

2. **Backend CORS** must allow the UI origin:

   ```env
   CORS_ORIGINS=["https://mint-analytics-new.minchy.ai"]
   ```

3. Do **not** expect `/api/v1` on the UI host to work unless you add a reverse proxy there. The browser should call the **API host** only.

4. **HRIS launch auth** (MinHRM widget → `/auth?payload=`):

   ```env
   HRIS_LAUNCH_SECRET_KEY="<exact same base64 string as PHP self::$secretKey>"
   # Quote the value if it contains '+' (otherwise Docker/shell may mangle it → "Invalid HRIS launch secret encoding").

   **ETL source save (POST /tenants/etl-sources/)** requires a stable Fernet key (same on every API replica):

   ```env
   DB_ENCRYPTION_KEY="<Fernet key — generate once, keep forever>"
   ```

   Without it the API returns **503** (or **500** on older builds). Generate:

   ```bash
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```
   HRIS_WAREHOUSE_PERMISSION=warehouse_access
   ```

   PHP uses `base64_decode(self::$secretKey)` as the AES-256 key. Put the **same base64 string** (not the decoded bytes) in the API env. A placeholder dev key will cause **`AES decrypt failed`** for real HRIS payloads.

   **Key rotation:** PHP and the API must use the **same** key at encrypt and decrypt time. If PHP rotates `self::$secretKey`, set both on the API during overlap:

   ```env
   HRIS_LAUNCH_SECRET_KEYS=<new_php_key>,<old_php_key>
   ```

   Do not regenerate the launch secret per request or per session — use a stable value from env/DB. Rotate only on a schedule and update the API when PHP changes.

   MinHRM `actionLaunchAnalytics` encrypts `token` (one-time `auth_code` from `generateSecureCode`), `subdomain`, `user_emp_id`, and `company_logo_url`. That `token` changes every launch; only `PythonPayroll` AES `secretKey` must stay in sync with `HRIS_LAUNCH_SECRET_KEY`.

   Verify after deploy:

   ```bash
   cd backend
   python tools/verify_hris_launch_secret.py --payload "PASTE_PAYLOAD_FROM_URL"
   ```

5. Verify: `curl -H "X-API-Key: ..." -H "X-Tenant-Id: demo_tenant" https://mint-analytics-new-api.minchy.ai/api/v1/tenants/source`

6. **Datamart LLM (required for `/datamart/chat`)** — copy the **same** AI block from your working `backend/.env` into production secrets:

   ```env
   EXPERIENCE_LLM_BACKEND=ollama
   EXPERIENCE_LLM_USER=mint-analytics-dev
   OLLAMA_URL=https://ai-core.minchy.ai
   OLLAMA_MODEL=gpt-oss:20b
   OLLAMA_AUTH=<same Base64 Basic auth as local>
   DATAMART_CHAT_MODEL=gpt-oss:20b
   DATAMART_LLM_MODEL=gpt-oss:20b
   ```

   If you use Minchy proxy instead: `EXPERIENCE_LLM_BACKEND=minchy` and a valid `MINCHY_AI_API_KEY` (not empty / not `CHANGE_ME`).

   Check from the API host:

   ```bash
   curl -s https://mint-analytics-new-api.minchy.ai/health | jq .checks.datamart_llm
   ```

   Expect `"status": "ok"`. If `http_401` → fix `OLLAMA_AUTH` or API key. If `error` / timeout → firewall / egress to `ai-core.minchy.ai`.

`frontend/src/env.ts` also maps `mint-analytics-new.minchy.ai` → the API subdomain at runtime if the build still uses `/api/v1`.

---

See **[docs/TENANT_ONBOARDING.md](docs/TENANT_ONBOARDING.md)** for the standard two-table flow (registry at onboarding, sources from UI).

## Tenant data model (control plane vs source DBs)

Industry practice for multi-tenant analytics is a **control-plane registry** (who the tenant is, where their warehouse lives) separate from **connection credentials** for customer source systems ([control plane separation](https://letsbuildsolutions.com/blog/system-design/designing-a-multi-tenant-saas-backend-isolation-strategies-schema-design-and-scaling-patterns/)).

MintHRM maps that as follows:

| Store | Database | Purpose |
|-------|----------|---------|
| **Tenant registry** | Application DB `hrm_control.tenant_registry` | `tenant_id`, `display_name`, `is_active`, **warehouse** routing (`warehouse_db`, `warehouse_host`, …). Legacy `mysql_*` columns exist for old flows; placeholders are OK until UI sources exist. |
| **ETL source registry** | Application DB `hrm_control.tenant_etl_sources` | Per-tenant source keys, primary flag, link to saved connection (`connection_id`). |
| **Encrypted source credentials** | Tenant **warehouse** DB `database_connections` | Host, user, password (Fernet), schema — what you add in **Settings → Source Databases**. |

**HRIS launch (`/auth?payload=`)** only checks that `subdomain` exists in `tenant_registry` and `is_active = true`. It does **not** require customer source DB details in that table.

**POST `/tenants/etl-sources/`** writes source credentials + `tenant_etl_sources`. A **500/duplicate key** on that endpoint means `source_key` already exists (e.g. `uat_for_amazon` for `etsteasuat`) — not a missing registry row.

### Minimal tenant provision (no source DB)

```bash
curl -X POST \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"tenant_id": "etsteasuat", "display_name": "ET STEAS UAT"}' \
  https://mint-analytics-new-api.minchy.ai/api/v1/tenants/provision-minimal
```

Then add MySQL/PostgreSQL sources in the UI. Optional: `HRIS_LAUNCH_AUTO_PROVISION_TENANT=true` creates the minimal registry row on first successful HRIS decrypt (off by default in production).

---

## Onboarding a New Customer (Tenant)

### 1. Register the tenant

```bash
curl -X POST \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "acme_corp",
    "display_name": "ACME Corporation",
    "source_type": "mysql",
    "mysql_host": "mysql.acme.internal",
    "mysql_port": 3306,
    "mysql_db": "minthrm_acme",
    "mysql_user": "readonly_user",
    "mysql_password": "secret"
  }' \
  http://localhost:8001/api/v1/tenants/
```

For **PostgreSQL** sources, set `"source_type": "postgres"` and port `5432`. Connection fields still use `mysql_*` keys in the API (legacy column names).

Local dev registration from `backend/.env`:

```bash
# SOURCE_TYPE=mysql|postgres, SOURCE_HOST, SOURCE_DB, ...
python scripts/register_tenant.py
```

### 2. Run initial ETL (full load)

```bash
curl -X POST \
  -H "X-API-Key: $API_KEY" \
  -H "X-Tenant-Id: acme_corp" \
  -H "Content-Type: application/json" \
  -d '{"run_type": "full_load", "triggered_by": "onboarding"}' \
  http://localhost:8001/api/v1/hr-etl/run
```

This will:
1. Create 4 schemas: `acme_corp_hr_raw`, `acme_corp_hr`, `acme_corp_hr_semantic`, `acme_corp_hr_control`
2. Extract all HR tables from the tenant source DB → staging
3. Run dbt transforms → dimensional mart
4. Build semantic views (AI-safe layer)

### 3. Verify ETL

```bash
curl -H "X-API-Key: $API_KEY" -H "X-Tenant-Id: acme_corp" \
  http://localhost:8001/api/v1/hr-etl/status
```

### 4. Test HR query

```bash
curl -X POST \
  -H "X-API-Key: $API_KEY" \
  -H "X-Tenant-Id: acme_corp" \
  -H "Content-Type: application/json" \
  -d '{"question": "What is our headcount?"}' \
  http://localhost:8001/api/v1/experience/ask
```

---

## Architecture — DO NOT VIOLATE

### Data Flow

```
MintHRM MySQL (per customer, read-only)
  ↓ Python EL (extractors.py)
{tenant}_hr_raw (staging mirror)
  ↓ dbt 1.8 (hr_mart project)
{tenant}_hr (dimensional mart)
  ↓ dbt views
{tenant}_hr_semantic (AI-safe views, ai_reader role only)
  ↓ FastAPI (MetricResolver)
/hr/*  /experience/*
  ↓ React 18 + TypeScript
HR Reports · Experience Console
```

### Key Invariants

1. **AI never touches raw data** — `ai_reader` role has SELECT-only on `*_hr_semantic.vw_*`
2. **No dynamic SQL in AI layer** — all queries map to existing MetricResolver calls
3. **Every endpoint requires** `Depends(verify_api_key)`
4. **Tenant isolation** — every query is scoped to `{tenant_id}_hr` schema via `search_path`
5. **MySQL is read-only** — ETL uses a dedicated read-only MySQL user per tenant
6. **Passwords encrypted** — MySQL passwords stored Fernet-encrypted in `hrm_control.tenant_registry`

---

## Scheduled ETL (Production)

Add to crontab or APScheduler:

```python
# backend/app/services/hr_etl/scheduler.py
from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler()

# Run incremental ETL for all active tenants every 4 hours
scheduler.add_job(run_all_tenants_incremental, "interval", hours=4)
scheduler.start()
```

---

## Adding a New HR Metric

1. Add entry to `backend/app/rules/hr_semantic/hr_metrics.yaml`
2. Add corresponding column to the relevant `vw_*` semantic view in dbt
3. Run `dbt run --select semantic.*` for affected tenants
4. The metric is immediately available via `/api/v1/hr/metric/{name}`

No code changes required — the MetricRegistry hot-reloads on file mtime change.
