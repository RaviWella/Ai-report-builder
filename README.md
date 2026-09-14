# MintHRM — HR Intelligence Platform

**Version:** v1.0.0 — Foundation Release

Governance-grade HR analytics built on customer source databases (MySQL and/or PostgreSQL).
Every metric is traceable to posted HR transactions via the mart and semantic views.
Runtime contracts, taxonomy, and output semantics are frozen as of v1.0.

**Multi-tenant:** one PostgreSQL **warehouse database** per customer (`hrm_wh_{tenant_id}`) on the analytics cluster, with schemas `hr_raw`, `hr`, `hr_semantic`, `hr_control`. Platform metadata lives in a separate **application** database (`hrm_platform`).

---

## Architecture

```
Customer source DB(s) — MySQL / PostgreSQL (read-only, per tenant)
  ↓ Python EL (extract → warehouse hr_raw.stg_*)
hr_raw  — staging mirror
  ↓ dbt
hr      — dimensional mart (dim_*, fact_*)
  ↓ dbt views
hr_semantic  — AI-safe views (ai_reader role)
  ↓ FastAPI
/hr/*  /hr-etl/*  /datamart/*
  ↓ React 18 + TypeScript + Vite
HR Reports · Datamart Assistant · ETL Control
```

**Datamart ER documentation:** When you add, rename, or remove dbt mart/semantic models or change join grains, update [`docs/datamart-er.yml`](docs/datamart-er.yml) and regenerate [`docs/HR_DATAMART_ER.pdf`](docs/HR_DATAMART_ER.pdf). See [`docs/README.md`](docs/README.md).

### Datamart AI Assistant (text-to-SQL)

Ad-hoc analytics on a **read-only analytics warehouse** (separate from the per-tenant HR marts). Uses LLM-generated SQL with grounding, SQL safety checks, sessions/templates, and report export.

| Surface | Path |
|---|---|
| UI | `/datamart/chat` (nav: **Datamart Assistant**) |
| API | `/api/v1/datamart/*` |

**Setup (after `docker compose up`):**

1. Apply migrations (creates chat/workspace tables in **`public` only**; revision `dm_public_consolidate_001` merges any legacy copies from tenant marts and drops them):

   ```bash
   cd backend && alembic upgrade heads
   python tools/check_datamart_tables.py   # optional sanity check
   ```

2. Copy datamart block from `backend/.env.example` into `backend/.env` — warehouse credentials (`DATAMART_*`), optional `DATAHUB_GMS_URL`, and `AI_PROXY_API_KEY` / `MINCHY_AI_API_KEY` for the LLM.

3. Optional metadata: see [DATAHUB_SETUP.md](DATAHUB_SETUP.md). After warehouse or datamart agent/catalog changes, refresh metadata:

   ```powershell
   # From repo root (Windows)
   .\scripts\refresh_datamart_metadata.ps1

   # Metadata + datamart unit tests
   .\scripts\after_datamart_change.ps1

   # Or before starting the API
   cd backend
   .\run-dev.ps1 -RefreshMetadata
   ```

   Credentials for DataHub ingest are read from `backend/.env` (`DATAMART_*`, `DATAHUB_GMS_URL`); a generated `datahub_ingestion.generated.yml` is not committed.

4. Frontend: `X-API-Key` only for `/api/v1/datamart/*` (no `X-Tenant-Id` required).

**Datamart LLM 401 / no responses on localhost:** (1) Use hosted Ollama settings in `backend/.env` (same as mint-analytics). (2) On Windows, an **old `python.exe` on `127.0.0.1:8000`** can steal traffic from your new uvicorn — run `.\tools\clear-port-8000.ps1` then restart. (3) You should see `Datamart LLM ready: backend=ollama` and `→ POST /api/v1/datamart/chat` in the terminal when logging is enabled.

**Note:** Datamart Assistant uses a read-only analytics warehouse (`DATAMART_SCHEMA`, default `public_mint_audit`), separate from per-tenant HR marts (`hr_semantic` views).

**Tests:**

```bash
# Backend (pytest-sugar progress bar; install once: pip install pytest pytest-asyncio pytest-sugar)
cd backend && python -m pytest -m datamart
cd frontend && npm run test
# E2E (dev server on :5174, API on :8000):
cd frontend && npm run test:e2e -- e2e/datamart-workspace-nav.spec.ts
```

**Phase 6b DataHub per tenant** (after ETL warehouse exists):

```bash
cd backend
python tools/run_tenant_datahub_ingest.py --tenant-id demo_tenant
# Or full metadata refresh (DataHub + semantic catalog):
cd .. && .\scripts\refresh_datamart_metadata.ps1 -TenantEtl -TenantId demo_tenant
```

**Phase 7 registry warehouse** — set `DATAMART_USE_TENANT_REGISTRY=true` in production so datamart uses `hrm_control.tenant_registry` only (no duplicate `DATAMART_DB_*`). Dev can keep `false` and point `DATAMART_DB_NAME` at `hrm_wh_*`.

**Phase 9 JWT auth** — production: `MOCK_AUTH_ENABLED=false`, send `Authorization: Bearer <token>` (tenant + user in claims). Dev token:

```bash
cd backend
python tools/create_dev_jwt.py --tenant-id demo_tenant --user-id my-user --print-curl
```

Frontend: set `REACT_APP_AUTH_TOKEN` to the JWT. Datamart dev without login: `MOCK_AUTH_ENABLED=true` and `DATAMART_REQUIRE_TENANT_HEADER=false`.

**Phase 11 per-tenant semantic catalog** (ETL warehouses):

```bash
cd backend
python tools/semantic_catalog_tool.py refresh --tenant demo_tenant --write
python tools/semantic_catalog_tool.py validate --tenant demo_tenant
# Or with metadata refresh:
cd .. && .\scripts\refresh_datamart_metadata.ps1 -TenantEtl -TenantId demo_tenant
```

Catalogs live under `backend/app/services/ai_services/datamart/semantic_catalogs/{tenant_id}.yaml`.
Until generated, tenant ETL falls back to `semantic_catalog.yaml`.

**Full phase verification** (migrations + tests + live smoke):

```powershell
.\scripts\verify_datamart_phases.ps1
# With API running:
.\scripts\verify_datamart_phases.ps1 -ApiUrl http://127.0.0.1:8000
```

**Phase 10 live smoke** (real warehouse + optional running API):

```powershell
# After alembic upgrade head and DATAMART_DB_* → hrm_wh_demo_tenant
cd backend
python tools/smoke_datamart_phase10.py
# With API on :8000
..\scripts\smoke_datamart_phase10.ps1 -ApiUrl http://127.0.0.1:8000
# Pytest (opt-in)
$env:DATAMART_LIVE_TEST = "1"
python -m pytest tests/datamart/test_live_smoke.py -m live -v
```

### 4 PostgreSQL Schemas (per tenant)

| Role | Database | Host (production) | Contents |
|------|----------|-------------------|----------|
| **Application** | `hrm_platform` | Control-plane Postgres | `hrm_control.*` — tenants, ETL sources, registry |
| **Warehouse** | `hrm_wh_{tenant_id}` | **Separate** analytics Postgres | Staging, marts, semantic views, ETL run logs |
| **Source** | Customer DB | Customer network | Upstream HR data (configured in UI) |

**Provisioning (default):** application DB is created by DBA / Docker `init-db.sh` (`APP_AUTO_PROVISION=false`). Per-tenant warehouse DBs are auto-created on first ETL or tenant register (`WAREHOUSE_AUTO_PROVISION=true`).

See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for production split-server setup and [backend/.env.production.example](backend/.env.production.example).

### Warehouse layers (per tenant)

Default isolation (`WAREHOUSE_DEFAULT_ISOLATION=database`):

| Layer | Schema | Purpose | Access |
|-------|--------|---------|--------|
| Raw | `hr_raw` | Source mirror (`stg_*`) | ETL only |
| Mart | `hr` | Dimensional mart (`dim_*`, `fact_*`) | Backend |
| Semantic | `hr_semantic` | AI-safe views (`vw_*`) | Backend + `ai_reader` |
| Control | `hr_control` | ETL governance, watermarks | Backend |

Legacy mode (`WAREHOUSE_DEFAULT_ISOLATION=schema`): prefixed schemas `{tenant_id}_hr*` on the application Postgres instance.

---

## Platform layers (v1.0)

### Ingestion
Multi-source ETL: MySQL and/or PostgreSQL per tenant (Settings → **ETL Sources**). Watermark-based incremental loads. Multiple sources per tenant supported (product scenarios A/B/C in UI).

### HR Intelligence Core
Deterministic, auditable analytics. No LLM at runtime for core metrics.

| Component | Purpose |
|-----------|---------|
| `MetricResolver` | Resolves HR metrics from semantic views |
| `ReportBuilder` | Headcount · Turnover · Payroll · Attendance · Leave |
| `IntentEngine` | Rules-based classifier — no LLM |
| `TimeResolver` | YAML-driven, period-aware resolution |
| `Planner` | Maps intents to existing service calls |
| `Composer` | Executes plans, generates structured answers |
| `DriverService` | Variance decomposition |

---

## Quick Start

```bash
# 1. Environment
cp backend/.env.example backend/.env
# Edit backend/.env — APPLICATION_DATABASE_URL, DB_ENCRYPTION_KEY, source DB if using register_tenant.py

# 2. Docker (creates hrm_platform via init-db.sh; warehouse DBs on first ETL)
docker compose up -d --build

# 3. Migrations — run automatically on API startup (Alembic upgrade head).
#    Optional manual run: cd backend && alembic upgrade head

# 4. Optional: register legacy tenant source from .env
python scripts/register_tenant.py

# 5. Backend (Python 3.11 + SQLAlchemy 2.x on your machine)
cd backend
python -m pip install -r requirements.txt
$env:PYTHONPATH = "."
cd backend
$env:PYTHONPATH = "."
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
# Or: .\run-dev.ps1  (same command + SQLAlchemy version check)

# 6. Verify
curl http://localhost:8000/health
# UI: http://localhost:5174 — ETL Sources → ETL Control → Run ETL
```

**Production:** copy `backend/.env.production.example` → `backend/.env`, set `MIGRATION_FAIL_FAST=true`, `RUN_MIGRATIONS_IN_ENTRYPOINT=true`, `RUN_MIGRATIONS_ON_STARTUP=false`, separate app and warehouse hosts. The backend image entrypoint runs `alembic upgrade head` once before uvicorn; Jenkins **Verify Deployment Health** waits for `/health` before marking the pipeline successful.

---

## Key invariants (DO NOT BREAK)

1. AI never touches raw data — `ai_reader` role has SELECT-only on `*_hr_semantic.vw_*`
2. HR report APIs use semantic views and `HrMetricResolver` — no ad-hoc SQL from the UI (Datamart Assistant uses read-only warehouse SQL in a separate, guarded pipeline)
3. Every endpoint requires `Depends(verify_api_key)`
4. `Answer.to_dict()` output shape is frozen
5. `OntologyStore` taxonomy frozen as of v1.0
6. `rules_sha` must appear on every mart row — audit backbone
7. Source connectors: MySQL or PostgreSQL per tenant (`source_type` + ETL Sources UI)
8. Multi-tenant warehouse: one `hrm_wh_{tenant_id}` database (default) or `{tenant_id}_hr*` schemas (legacy)

---

## Documentation

| Doc | Purpose |
|-----|---------|
| [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) | Docker, migrations, production DB split, ETL scenarios |
| [backend/.env.example](backend/.env.example) | Local / dev environment template |
| [backend/.env.production.example](backend/.env.production.example) | Production template (split app + warehouse servers) |
