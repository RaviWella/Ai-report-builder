# MintHRM — AI-Assisted Report Builder

> Developer build guide. Read this top-to-bottom before writing code.
> Companion documents: `SRS v0.2` (functional spec) and `Technical Architecture v1.0` (full detail + diagrams).

---

## 1. What we are building

A new MintHRM module that lets a **non-technical user** (client HR admin, or MintHRM support) design, preview, and publish custom HR reports from a client's data — **with zero developer involvement**.

Two panels:

- **Builder panel** — design and publish report templates.
- **Viewer panel** — end-users run published reports, apply filters, download Excel/PDF.

Reports are built either by **chatting with an AI assistant**, by **uploading a sample Excel layout**, or by mixing both freely in one session. Output is branded Excel and PDF, with filtering, grouping, scheduling and audit.

---

## 2. Non-negotiable rules

These are the architectural guarantees. **Do not break them, even if a shortcut looks easier.**

1. **Nobody touches raw schema directly.** All report logic goes through the **semantic layer** (business names → physical columns). The AI and the query engine both resolve fields through it.
2. **The AI never writes SQL.** The AI returns a **structured spec** (JSON: fields, filters, grouping). Only the **Query Engine** turns a spec into SQL.
3. **The AI never receives PII.** The AI sees metadata only — column headers, inferred types, semantic field names, the current spec. **Never employee records.** Strip Excel data rows *before* any AI call.
4. **The spec is the source of truth; SQL is a compiled artifact.** SQL is generated from the spec and may be cached, but is never hand-edited. If cache is missing/stale → regenerate from the spec.
5. **All SQL is parameterized and tenant-scoped.** No string concatenation. Tenant scope is enforced **server-side in the Query Engine**, never by the UI. Reporting uses a **read-only DB user on a read replica**.
6. **Every report run and template change is audited.**

---

## 3. Tech stack & libraries

> **Version policy:** pins below are **major versions** known-good as of 2026. At project init, pin the *latest stable patch* within each major in `pyproject.toml` / `package.json`, then update deliberately.

### 3.1 API style — REST (decision: **REST, not GraphQL**)

The API is **REST/JSON over FastAPI**. GraphQL was considered and rejected for this product:

- **Query flexibility already lives in the report spec.** The "which fields / filters" dynamic part is the `data_spec` JSON, *not* a client query language. Adding GraphQL would duplicate that flexibility in two places.
- **Most operations are actions, not graph reads** — `run report`, `publish version`, `upload excel`, `trigger schedule`. These map cleanly to REST endpoints (`POST /reports/{id}/run`).
- **Security is simpler in REST** — tenant scoping, RBAC, rate limiting and audit are per-endpoint dependencies; GraphQL's single endpoint needs depth/field-level guards for the same guarantees.
- **FastAPI gives auto OpenAPI docs + typed Pydantic models + frontend type generation** for free.

> If external/partner integrations later demand it, a GraphQL gateway can be added *in front of* REST. Not now — it would be over-engineering.

### 3.2 Backend libraries (Python 3.13)

| Library | Version | Used for |
|---|---|---|
| `fastapi` | ^0.115 | Web framework, routing, dependency injection |
| `pydantic` | ^2 | Spec models, request/response validation, settings |
| `uvicorn` | ^0.34 | ASGI server (dev + worker base) |
| `gunicorn` | ^23 | Production process manager for Uvicorn workers |
| `sqlalchemy` | ^2.0 | **Core** query building — parameterized SQL (no ORM, no raw strings) |
| `psycopg` | ^3.2 | PostgreSQL driver; separate read-only pool for the replica |
| `alembic` | ^1.14 | Metadata DB schema migrations |
| `pandas` | ^2.2 | Excel parse + local type inference (rows stripped before AI) |
| `openpyxl` | ^3.1 | Reading uploaded `.xlsx` layouts |
| `xlsxwriter` | ^3.2 | Branded, formatted Excel export |
| `weasyprint` | ^63 | HTML/CSS → PDF export (branded) |
| `celery` | ^5.4 | Async jobs + scheduled runs (with Celery Beat) |
| `redis` | ^5.2 | Redis client (cache + Celery broker/backend) |
| `authlib` *(or `python-jose`)* | ^1.4 | OAuth2 / JWT handling |
| `passlib[bcrypt]` | ^1.7 | Password hashing |
| `structlog` | ^24 | Structured logging |
| `httpx` | ^0.28 | Outbound calls to the AI provider |
| `anthropic` | ^0.40 | Default AI provider SDK (swappable behind the adapter) |
| `opentelemetry-sdk` | ^1.29 | Tracing across API → query → render |
| `pytest`, `pytest-asyncio` | ^8 / ^0.25 | Backend tests |

> **Self-hosted AI option:** `vllm` for serving an open-weight model (Llama/Mistral), reached through the same `AIProvider` interface — no core code changes.

### 3.3 Frontend libraries (React 19 + TypeScript, Node 24 LTS)

| Library | Version | Used for |
|---|---|---|
| `react`, `react-dom` | ^19 | UI framework |
| `typescript` | ^5.7 | Type safety (mirrors backend Pydantic specs) |
| `vite` | ^6 | Build tool + dev server |
| `@tanstack/react-query` | ^5 | Server state, API caching |
| `zustand` | ^5 | Builder working-state (lightweight; RTK if preference) |
| `@dnd-kit/core` | ^6 | Drag-drop field selector + column reordering |
| `@radix-ui/*` *(or `@mui/material`)* | latest | Accessible UI primitives / components |
| `react-hook-form` + `zod` | ^7 / ^3 | Form state + client-side validation |
| `axios` *(or fetch)* | ^1.7 | API client (typed wrapper) |
| `recharts` | ^2 | Optional basic visual summaries (later) |
| `vitest`, `@playwright/test` | ^2 / ^1.49 | Unit + e2e tests |

### 3.4 Infrastructure

| Component | Version | Used for |
|---|---|---|
| PostgreSQL (metadata DB) | 16 / 17 | Semantic layer, report defs, versions, audit |
| PostgreSQL (datamart) | existing (18) | Reporting source — **read replica, read-only user** |
| Redis | ^7 | Cache + Celery broker |
| Nginx | ^1.27 | TLS termination, routing, rate limiting |
| Docker + Compose | latest | Reproducible environments (K8s optional for prod) |
| GitHub Actions | — | CI/CD (lint, test, build, deploy) |
| Prometheus + Grafana + Sentry | latest | Metrics, dashboards, error tracking |

---

## 4. Architecture at a glance

```
Browser (Builder SPA, Viewer SPA)
        │ HTTPS
   Nginx (TLS, routing, rate limit)
        │ REST/JSON
   FastAPI backend
   ├─ Auth & Tenant Guard
   ├─ Semantic Layer Service
   ├─ AI Adapter ───────────► AI provider  (metadata only, NO PII)
   ├─ Query Engine ─────────► Datamart read replica (read-only)
   ├─ Rendering Engine (Excel / PDF)
   └─ Scheduler API
   Celery Worker (async exports, scheduled runs)  ◄─► Redis
   Metadata DB (PostgreSQL): semantic layer, report defs, versions, audit
```

See `Technical Architecture v1.0` for the full diagrams (system, build-time, run-time, security).

---

## 5. Data model (metadata DB — schema-per-tenant)

PostgreSQL uses **schema-per-tenant** isolation (payroll-platform pattern). See [docs/architecture/SCHEMA_PER_TENANT_MIGRATION_PLAN.md](docs/architecture/SCHEMA_PER_TENANT_MIGRATION_PLAN.md).

| Schema | Tables | Purpose |
|---|---|---|
| `platform` | `tenant_provision_status`, `ai_provider_configs_system` | Cross-tenant control plane |
| `public` | Template DDL (cloned per tenant) | Alembic Phase 1 target |
| `{tenant}` | All app tables below | Per-customer data via `search_path` |

| Table (per tenant schema) | Key columns | Purpose |
|---|---|---|
| `semantic_models` | id, version, catalog (JSONB) | Versioned semantic layer |
| `report_templates` | id, name, current_published_version_id, created_by | Logical report |
| `report_template_versions` | id, template_id, version_no, data_spec (JSONB), presentation_spec (JSONB), semantic_version_ref, status | Immutable version snapshots |
| `report_schedules` | id, template_id, cron, recipients, format, enabled | Scheduled delivery |
| `ai_sessions` | id, template_id, messages (JSONB), created_by | Build-time chat |
| `audit_log` | id, user_id, action, target_type, target_id, detail (JSONB), created_at | Immutable audit |
| `sql_cache` (optional) | version_id, sql_text, semantic_version_ref | Cached compiled SQL |

**New empty database:** run `alembic upgrade head` (greenfield baseline `0001_schema_per_tenant_baseline`). Manual tenant setup and data queries: [backend/scripts/sql/schema_per_tenant_manual.sql](backend/scripts/sql/schema_per_tenant_manual.sql). See [docs/architecture/REPORT_BUILDER_PG_ER.md](docs/architecture/REPORT_BUILDER_PG_ER.md).

---

## 6. The report definition (the heart of the system)

A template version stores **two JSONB blobs**. Keep them separate: presentation can change without rebuilding the query, and vice-versa.

### 6.1 `data_spec` — drives the Query Engine

```json
{
  "entity": "Employee",
  "fields": [
    { "ref": "employee.full_name", "label": "Employee Name" },
    { "ref": "department.name",     "label": "Department" },
    { "ref": "employee.join_date",  "label": "Joined" },
    { "ref": "payroll.basic",       "label": "Basic Salary", "agg": null }
  ],
  "filters": [
    { "ref": "employee.status", "op": "eq", "value": "active" },
    { "ref": "employee.join_date", "op": "between", "param": "join_range" }
  ],
  "group_by": ["department.name"],
  "aggregations": [
    { "ref": "payroll.basic", "fn": "sum", "label": "Total Basic" }
  ],
  "sort": [{ "ref": "department.name", "dir": "asc" }],
  "runtime_params": [
    { "name": "join_range", "type": "date_range", "required": false }
  ]
}
```

> `ref` values are **semantic-layer references**, never physical table/column names. Filter values entered at run-time arrive as **bound parameters** (`param`/`runtime_params`), never inlined.

### 6.2 `presentation_spec` — drives the Rendering Engine

```json
{
  "title": "Active Employees by Department",
  "branding": { "logo_id": "tenant_logo", "header": "...", "footer": "Confidential" },
  "columns": [
    { "ref": "employee.full_name", "width": 220 },
    { "ref": "payroll.basic", "format": "currency", "align": "right" }
  ],
  "conditional_formats": [
    { "ref": "payroll.basic", "when": "gt", "value": 100000, "style": "highlight" }
  ],
  "page": { "orientation": "portrait", "totals": true }
}
```

### 6.3 Spec → SQL (Query Engine pipeline)

```
data_spec + runtime params
   → resolve refs via semantic layer (pinned version)
   → SQLAlchemy Core query build (parameterized)
   → apply tenant scope + row limit + statement timeout   [guards.py]
   → execute on read replica
   → rows
```

---

## 7. Folder structure (monorepo)

```
backend/
├─ app/
│  ├─ main.py
│  ├─ core/            # config, security (JWT/RBAC), tenancy, logging
│  ├─ api/v1/          # routers: templates, reports, semantic, ai, exports, schedules
│  ├─ domain/          # pure models: report_spec, semantic, enums
│  ├─ services/        # template_service (versioning), semantic, ai, audit
│  ├─ query_engine/    # compiler, sql_builder (SQLAlchemy Core), filters, guards
│  ├─ rendering/       # excel_renderer, pdf_renderer, templates/
│  ├─ ai/              # base (AIProvider iface), anthropic_provider, selfhosted_provider, prompts/
│  ├─ ingestion/       # excel_parser (headers+types, rows stripped)
│  ├─ repositories/    # template_repo, semantic_repo, audit_repo
│  ├─ db/              # metadata.py, datamart.py (read-only pool)
│  └─ workers/         # celery_app, tasks, beat_schedule
│  └─ migrations/      # alembic
frontend/
├─ src/
│  ├─ features/builder/   # FieldSelector, FilterPanel, ChatAssistant, ExcelUpload, PreviewPane
│  ├─ features/viewer/    # run + download
│  ├─ features/templates/ # list + versions
│  ├─ api/  components/  hooks/  store/  types/
infra/    # docker-compose.yml, nginx/, k8s/
docs/     # SRS.md, architecture.md
```

---

## 8. Phased build plan

Build in this order — each phase is shippable and de-risks the next.

### Phase 0 — Foundations
- [ ] Monorepo, docker-compose (api, worker, redis, metadata DB, nginx)
- [ ] FastAPI skeleton + health check; React+Vite skeleton
- [ ] Auth (OAuth2/JWT), RBAC, tenant resolution + Tenant Guard
- [ ] Metadata DB + Alembic; read-only pool wired to the replica
- **Done when:** a logged-in user is correctly scoped to their tenant on every request.

### Phase 1 — Semantic layer + Query Engine *(highest-risk; do first)*
- [ ] Semantic model: schema introspection → editable catalog (entities, dimensions, measures, joins)
- [ ] `data_spec` model (Pydantic) + JSONB persistence
- [ ] Query Engine: spec → parameterized SQL (SQLAlchemy Core)
- [ ] Guards: tenant scope, row limit, statement timeout; execute on replica
- [ ] Run a hard-coded spec end-to-end → rows
- **Done when:** a spec returns correct, tenant-isolated rows with no raw SQL anywhere.

### Phase 2 — Builder UI (manual, no AI yet)
- [ ] Field selector (drag-drop), filter panel, grouping/sort, calculated fields
- [ ] `presentation_spec`: column formats, branding (header/footer/logo), conditional formats
- [ ] Live preview (sample rows)
- [ ] Save template → version snapshot (draft); publish flow
- **Done when:** a user builds, previews, and publishes a report by hand.

### Phase 3 — Rendering & export
- [ ] Excel renderer (XlsxWriter) with branding + formats
- [ ] PDF renderer (WeasyPrint)
- [ ] Viewer panel: list, run with runtime filters, download
- **Done when:** published reports download as branded Excel and PDF.

### Phase 4 — AI assistant
- [ ] AI Adapter + `AIProvider` interface (anthropic_provider first)
- [ ] Excel ingestion: parse headers, infer types (pandas), **strip rows**, suggest mapping → human confirm
- [ ] NL request → `data_spec`; adjustment chat → updated spec
- [ ] Interleave chat + Excel in one session
- **Done when:** a full report is built by chat alone, and by Excel-then-chat, with **no PII leaving the boundary**.

### Phase 5 — Scheduling, audit, hardening
- [ ] Celery Beat schedules → run + email delivery; async export jobs
- [ ] Audit log on all runs/exports/template changes
- [ ] Versioning polish (rollback, semantic-version pinning)
- [ ] Observability, rate limits, load test on replica
- **Done when:** scheduled reports deliver, everything is audited, and the system is production-ready.

---

## 9. Local dev setup

```bash
# 1. clone, then bring up infra
cd infra && docker compose up -d        # api, worker, redis, metadata db, nginx

# 2. backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e .
alembic upgrade head
uvicorn app.main:app --reload

# 3. frontend
cd frontend
npm install
npm run dev
```

Environment: copy `.env.example` → `.env`. Required keys include metadata DB URL, **read-replica URL (read-only user)**, Redis URL, JWT secret, and AI provider key (only used by the AI Adapter).

---

## 10. Implementation gotchas

- **Read-only pool:** the datamart connection must use a read-only user and a *separate* pool from the metadata DB. Never run reporting queries on the primary.
- **Strip Excel rows in `ingestion/excel_parser.py` before the spec ever reaches the AI Adapter.** Type inference is local (pandas), not an AI task.
- **Semantic version pinning:** store `semantic_version_ref` on each template version so old reports regenerate correctly after the mapping changes.
- **Versioning trigger:** autosave drafts continuously; create an immutable version snapshot only on **publish**.
- **No `localStorage` assumptions in shared spec types** — keep TS `types/` mirroring the backend Pydantic spec models so both sides stay in sync.
- **Filter values are always bound parameters.** If you ever see a filter value inside an f-string, stop — that's a bug and a security hole.

---

## 11. Kick-off decisions still open

1. Metadata DB: separate instance vs separate database on existing infra.
2. Default AI provider + start ZDR + BAA contracting.
3. UI library (Radix/shadcn vs MUI) and state lib (Zustand vs Redux Toolkit).
4. Replica provisioning + read-only user (with DB team).
5. Semantic-layer introspection + enrichment process and ownership.
