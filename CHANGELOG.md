# MintHRM Intelligence Platform — Changelog

## v1.0.0 — Foundation Release (2026-05-15)

### What Shipped

**Backend**
- Multi-tenant PostgreSQL schema architecture (4 schemas per tenant: raw, mart, semantic, control)
- MySQL → PostgreSQL ETL pipeline with full-load and watermark-based incremental modes
- 11 MySQL table extractors: employees, departments, designations, branches, attendance, leave requests, leave types, payroll runs, payroll details, performance reviews, training records
- dbt 1.8 dimensional mart: dim_employee, fact_attendance, fact_payroll, fact_leave_balance
- 6 AI-safe semantic views: vw_headcount, vw_turnover, vw_attendance_summary, vw_payroll_summary, vw_leave_summary, vw_performance_summary
- HR Metric Registry (YAML-driven, hot-reload): 20 metrics across 6 categories
- MetricResolver: dimension_filter + formula metrics, safe formula evaluator
- ETL governance: run log, step log, watermarks, validation checks
- Experience Layer: deterministic fast router (6 HR tool routes), alignment handlers (identity, frustration, glossary), conversation orchestrator
- REST API: /tenants, /hr-etl, /hr/*, /experience/*
- Tenant registry with Fernet-encrypted MySQL passwords

**Frontend**
- Canvas-first workbench layout (mirrors mint-analytics v17.2)
- HR Dashboard with all 6 metric domains
- 6 dedicated report pages: Headcount, Turnover, Payroll, Attendance, Leave, Performance
- Experience Chat (canvas-first conversational workbench)
- ETL Control page (trigger runs, view run log, watermarks)
- MetricCard primitive with tone-aware value display
- Zustand workbench store (canvas, trail, narrative panel, session)

**Infrastructure**
- Docker Compose (PostgreSQL 15, FastAPI, React/Nginx)
- GitLab CI/CD (lint → test → build → deploy)
- Per-tenant schema isolation — 200+ customers supported

### Known Gaps (Phase 2)

- LLM router (Qwen/Claude) not wired — fast path + alignment handlers only
- SCD2 on dim_employee not implemented (SCD1 for now)
- Top-N ranking across departments/branches not implemented
- Driver analysis (why did turnover increase?) not implemented
- Training records mart model not built
- Disciplinary records not extracted
