> Source of truth: `MintHRM_Technical_Architecture.docx`. This Markdown mirror is for in-repo reference (Architecture §8.3).

MintHRM

Human Resource Management Platform

Technical Architecture Document

AI-Assisted Self-Service Report Builder

Audience: Development team

Companion to: SRS v0.2

Version: 1.0 (Draft)

Confidential – Internal use only


# Document Control

Field

Detail

Document title

Technical Architecture Document – AI-Assisted Report Builder

Audience

Development team (backend, frontend, DevOps)

Companion document

SRS v0.2 (functional specification)

Version

1.0 (Draft)

Status

For development planning


### Revision history

Version

Author

Summary

1.0

Architecture

Initial technical architecture for development


# Table of Contents


# 1. Introduction


## 1.1 Purpose

This document describes the technical architecture for the AI-Assisted Self-Service Report Builder, a new module of the MintHRM platform. It is intended for the development team and covers the technology stack, components and their responsibilities, build-time and run-time workflows, the data model, security architecture, the recommended project/folder structure, and deployment. It complements the SRS, which defines the functional requirements.


## 1.2 Architectural principles

Semantic layer first: no component — human or AI — works against raw physical schema; everything goes through a governed metadata layer.

Deterministic SQL: only the Query Engine generates SQL, always parameterized and tenant-scoped. The AI never emits SQL.

AI sees metadata only: the AI receives field names, types and specs — never employee records (PII).

Spec is the source of truth: a report is its definition (data spec + presentation spec); SQL is a compiled, reproducible artifact.

Separation of concerns: authoring, querying, rendering, scheduling and AI are independent modules behind clear interfaces.


# 2. Architecture Overview

The system is a multi-tenant web application layered over the existing PostgreSQL datamart. The browser hosts two single-page applications (Builder and Viewer). A FastAPI backend exposes the REST API and contains the core modules. A separate metadata database stores the semantic layer, report definitions, versions and audit data. Reporting queries run against a read-only replica of the datamart. Redis backs caching and the Celery worker that handles scheduled runs and asynchronous exports. The AI provider is reached only through the AI Adapter and only ever receives metadata.

Figure 1 — System architecture (component and data-flow overview)

Request style: synchronous REST/JSON for interactive operations (build, preview, run-on-demand); asynchronous jobs via Celery for scheduled reports and large exports.


# 3. Technology Stack

Versions below reflect current stable releases as of 2026; pin the latest stable/LTS at project initialisation.


## 3.1 Frontend

Concern

Choice

Notes

Language / framework

React 19 + TypeScript

Type safety mirrors backend spec models.

Build tooling

Vite (Node.js 24 LTS)

Fast dev server and builds.

Drag & drop

dnd-kit

Field selector and column reordering.

Server state

TanStack Query

API data fetching/caching.

Client state

Zustand (or Redux Toolkit)

Builder working state.

UI components

Radix UI / shadcn (or MUI)

Accessible primitives, theming.

Charts (optional)

Recharts

If basic visual summaries are added later.


## 3.2 Backend

Concern

Choice

Notes

Language

Python 3.13

Stable, strong data tooling.

Web framework

FastAPI + Pydantic v2

Typed, async, auto OpenAPI docs.

Server

Uvicorn behind Gunicorn

ASGI workers.

SQL building

SQLAlchemy Core

Parameterized, programmatic SQL (not ORM, not raw strings).

DB driver

psycopg 3

PostgreSQL access; separate read-only pool for the replica.

Excel parsing

pandas + openpyxl

Header + type inference; data rows stripped before AI.

Excel rendering

XlsxWriter

Branded, formatted .xlsx output.

PDF rendering

WeasyPrint (HTML/CSS → PDF)

ReportLab as alternative for pixel-level layouts.

Auth

OAuth2 / JWT (Authlib / python-jose)

RBAC + per-tenant claims.

Migrations

Alembic

Schema versioning for the metadata DB.


## 3.3 AI, async & infrastructure

Concern

Choice

Notes

AI (default)

External enterprise API (Anthropic) under ZDR + BAA

No training on data; metadata-only payloads.

AI (optional)

Self-hosted open-weight model (vLLM + Llama/Mistral)

For strict data-residency clients.

Async / scheduling

Celery + Celery Beat

Scheduled report runs, async exports, email delivery.

Cache / broker

Redis

Result cache and Celery broker/backend.

Metadata DB

PostgreSQL 16/17

Semantic layer, report defs, versions, audit.

Reporting source

Datamart read replica (PostgreSQL 18)

Existing store; read-only user.

Reverse proxy

Nginx

TLS termination, routing, rate limiting.

Containerisation

Docker + docker-compose; Kubernetes (prod, optional)

Reproducible environments.

Observability

structlog + Prometheus/Grafana + Sentry + OpenTelemetry

Logs, metrics, tracing, errors.

CI/CD & tests

GitHub Actions; pytest, Vitest, Playwright

Automated build/test/deploy.


# 4. Component Responsibilities


### 4.1 Frontend — Builder & Viewer SPAs

The Builder provides the authoring experience: field selector, filter panel, chat assistant, Excel upload, branding controls and live preview. The Viewer lists published reports, applies runtime filters and triggers downloads. Both are tenant-aware and role-aware; they never construct SQL and never assume cross-tenant access.


### 4.2 API & Auth / Tenant Guard

FastAPI routers expose the REST endpoints. The Auth layer verifies JWTs, enforces RBAC, and resolves the caller’s tenant. The Tenant Guard injects the tenant context that every downstream service and the Query Engine are bound to; tenant scope is enforced server-side, not by the UI.


### 4.3 Semantic Layer Service

Owns the metadata catalogue per tenant: entities (Employee, Department, Leave, etc.), dimensions, measures, and predefined joins. It is built by auto-introspecting the datamart schema and then enriched manually. Both the AI Adapter and the Query Engine resolve business names through this service.


### 4.4 AI Adapter

A provider-agnostic interface for the AI assistant’s three tasks (Excel mapping, natural-language request, adjustment chat). It assembles metadata-only payloads (headers, inferred types, semantic field names, current spec), calls the configured provider, and returns a structured specification or mapping suggestion. It enforces the rule that no PII and no SQL crosses this boundary.


### 4.5 Query Engine

The only component that produces and runs SQL. It compiles a data spec plus runtime filter parameters into parameterized, tenant-scoped SQL using SQLAlchemy Core, applies a row limit and statement timeout, executes on the read replica, and returns rows. Guards prevent cross-tenant references and any non-read operation.


### 4.6 Rendering Engine

Applies the presentation spec to query results to produce branded Excel (XlsxWriter) and PDF (WeasyPrint) outputs, including header/footer/logo, column formats and conditional formatting. Used both for on-demand downloads and for scheduled deliveries.


### 4.7 Scheduler & Celery Worker

Celery Beat triggers scheduled report definitions; the worker runs the report through the Query and Rendering engines and delivers the output (e.g. email). The same worker handles large/async exports so the API stays responsive. All runs are written to the audit log.


# 5. Workflows


## 5.1 Build-time

Creating or editing a template. Chat and Excel are interleavable input modes in a single session; the AI returns a specification that the user confirms; the finalised template is saved as an immutable version snapshot.

Figure 2 — Build-time workflow


## 5.2 Run-time

Running and exporting a published report. No AI participates; real data is processed only by the Query and Rendering engines, and the action is audited.

Figure 3 — Run-time workflow


# 6. Data Model (Metadata Database)

The application owns a dedicated PostgreSQL metadata database, separate from the datamart. Report definitions and the semantic layer are stored here; JSONB is used for the flexible spec structures. Core tables:

Table

Key columns

Purpose

tenants

id, name, status

Registered client organisations.

users

id, tenant_id, role, ...

Accounts and RBAC role per tenant.

semantic_models

id, tenant_id, version, catalog (JSONB)

Versioned semantic layer (entities, dimensions, measures, joins, physical mapping).

report_templates

id, tenant_id, name, current_published_version_id, created_by

Logical report; points to its published version.

report_template_versions

id, template_id, version_no, data_spec (JSONB), presentation_spec (JSONB), semantic_version_ref, status (draft/published), created_by, created_at

Immutable version snapshots; pinned to a semantic-layer version.

report_schedules

id, template_id, cron, recipients, format, enabled

Scheduled delivery configuration.

ai_sessions

id, template_id, messages (JSONB), created_by

Build-time chat history (not used at run-time).

audit_log

id, tenant_id, user_id, action, target_type, target_id, detail (JSONB), created_at

Immutable record of template changes and report runs/exports.

sql_cache (optional)

version_id, sql_text, semantic_version_ref

Cached compiled SQL; always reproducible from the spec.

Note: the SQL is never the source of truth. sql_cache is a performance optimisation only — if it is missing or stale it is regenerated from the data spec and the pinned semantic version.


# 7. Security Architecture

Security is layered (defense in depth). The two most important controls for this product are tenant isolation (enforced in the Query Engine) and the AI/PII boundary (enforced in the AI Adapter).

Figure 4 — Security architecture (defense in depth)


### 7.1 Tenant isolation

Every query is bound to the caller’s tenant schema server-side. A read-only database user with no DDL/DML rights is used for reporting. Each query carries a row limit and a statement timeout. Because scoping happens in the Query Engine, a compromised or buggy UI cannot reach another tenant’s data.


### 7.2 SQL safety

All SQL is built with parameterized queries through SQLAlchemy Core; user/filter values are bound parameters, never concatenated. The AI never produces SQL, removing the largest injection risk vector.


### 7.3 AI / PII boundary

The AI Adapter transmits only metadata and specifications. Uploaded Excel files have their data rows stripped locally before any AI call, and types are inferred with pandas rather than by the AI. The default external provider operates under a Zero Data Retention agreement and a Business Associate Agreement, with no training on customer data; a self-hosted model is available for clients whose contracts require it.


### 7.4 Identity, secrets & audit

Access uses OAuth2/JWT with short-lived tokens and RBAC. Secrets and DB credentials are held in a managed secret store and rotated. Data is encrypted in transit (TLS) and at rest. All template changes and report executions are written to an immutable, user-attributable audit log.


# 8. Recommended Project Structure

A monorepo with clearly separated backend, frontend and infrastructure. The backend layering keeps the deterministic Query Engine and the AI Adapter isolated from each other and from the HTTP layer.


## 8.1 Backend

backend/

├─ app/

│  ├─ main.py                  # FastAPI entrypoint

│  ├─ core/                    # cross-cutting concerns

│  │  ├─ config.py             # settings (env-driven)

│  │  ├─ security.py           # JWT, RBAC dependencies

│  │  ├─ tenancy.py            # tenant resolution & scope

│  │  └─ logging.py            # structured logging setup

│  ├─ api/                     # HTTP layer (routers only)

│  │  ├─ deps.py

│  │  └─ v1/

│  │     ├─ templates.py          # CRUD + versioning

│  │     ├─ reports.py            # run / preview

│  │     ├─ semantic.py           # semantic layer admin

│  │     ├─ ai.py                 # chat / mapping endpoints

│  │     ├─ exports.py            # excel / pdf

│  │     └─ schedules.py

│  ├─ domain/                  # pure models (no I/O)

│  │  ├─ report_spec.py        # data + presentation spec

│  │  ├─ semantic.py           # entity / dimension / measure

│  │  └─ enums.py

│  ├─ services/                # use-case orchestration

│  │  ├─ template_service.py   # version lifecycle

│  │  ├─ semantic_service.py

│  │  ├─ ai_service.py

│  │  └─ audit_service.py

│  ├─ query_engine/            # spec -> safe SQL (deterministic)

│  │  ├─ compiler.py

│  │  ├─ sql_builder.py        # SQLAlchemy Core, parameterized

│  │  ├─ filters.py

│  │  └─ guards.py             # tenant scope, limit, timeout

│  ├─ rendering/               # exports

│  │  ├─ excel_renderer.py

│  │  ├─ pdf_renderer.py

│  │  └─ templates/            # HTML/PDF branding templates

│  ├─ ai/                      # provider adapters

│  │  ├─ base.py               # AIProvider interface

│  │  ├─ anthropic_provider.py

│  │  ├─ selfhosted_provider.py

│  │  └─ prompts/              # metadata-only prompt templates

│  ├─ ingestion/               # excel upload

│  │  └─ excel_parser.py       # headers + types; rows stripped

│  ├─ repositories/            # metadata DB access

│  │  ├─ template_repo.py

│  │  ├─ semantic_repo.py

│  │  └─ audit_repo.py

│  ├─ db/

│  │  ├─ metadata.py           # app metadata DB session

│  │  └─ datamart.py           # read-only replica pool

│  └─ workers/                 # celery

│     ├─ celery_app.py

│     ├─ tasks.py              # scheduled runs, async export

│     └─ beat_schedule.py

├─ migrations/                 # alembic

├─ tests/

├─ pyproject.toml

└─ Dockerfile


## 8.2 Frontend

frontend/

├─ src/

│  ├─ app/                     # routing, providers

│  ├─ features/

│  │  ├─ builder/              # report builder

│  │  │  ├─ FieldSelector.tsx

│  │  │  ├─ FilterPanel.tsx

│  │  │  ├─ ChatAssistant.tsx

│  │  │  ├─ ExcelUpload.tsx

│  │  │  └─ PreviewPane.tsx

│  │  ├─ viewer/               # run + download

│  │  └─ templates/            # list + versions

│  ├─ api/                     # typed API client

│  ├─ components/              # shared UI

│  ├─ hooks/

│  ├─ store/                   # client state

│  └─ types/                   # TS types mirroring specs

├─ package.json

└─ Dockerfile


## 8.3 Infrastructure & docs

infra/

├─ docker-compose.yml          # dev: api, worker, redis, db, nginx

├─ nginx/                      # reverse proxy config

└─ k8s/                        # prod manifests (optional)

docs/

├─ SRS.md

└─ architecture.md

README.md


# 9. Deployment & Operations

Environments: local (docker-compose), staging, production. Identical container images promoted across environments.

Services: API (Uvicorn/Gunicorn), Celery worker, Celery Beat, Redis, metadata PostgreSQL, Nginx; the datamart read replica is provisioned by the DB team.

Scaling: API and worker scale horizontally; reporting load is isolated on the replica so it never affects the production primary.

Observability: structured logs, Prometheus metrics + Grafana dashboards, Sentry for errors, OpenTelemetry traces across API → query → render.

CI/CD: GitHub Actions runs lint, tests (pytest/Vitest/Playwright) and builds images on every merge; deploys are gated by passing checks.


# 10. Key Technical Decisions

#

Decision

Rationale

D1

Semantic layer as the foundation

Reliable AI suggestions and safe queries across 200 varied schemas; no direct raw-schema access.

D2

AI produces structured specs, never SQL

Eliminates SQL-injection and cross-tenant risk from AI output.

D3

AI receives metadata only, never PII

Privacy guarantee independent of provider choice.

D4

Report definition is source of truth; SQL is compiled

Prevents spec/SQL drift; enables safe regeneration and versioning.

D5

SQLAlchemy Core for parameterized SQL

Programmatic, safe SQL without an ORM’s overhead or raw strings.

D6

Reporting on a read replica with read-only user

Protects production; structurally blocks writes.

D7

Version-on-publish, autosave drafts

Clean version history with full rollback.

D8

Celery + Redis for async/scheduled work

Keeps the API responsive; supports scheduled delivery.

D9

Provider-agnostic AI adapter

Switch between external (ZDR+BAA) and self-hosted per client without touching core logic.


# 11. Open Items for Development Kick-off

Confirm metadata DB as a separate instance vs a separate database on existing infrastructure.

Confirm AI provider for the default deployment and initiate ZDR + BAA contracting.

Decide UI component library (Radix/shadcn vs MUI) and state library (Zustand vs Redux Toolkit).

Confirm replica provisioning and the read-only DB user with the database team.

Agree the semantic-layer introspection + enrichment process and ownership.
