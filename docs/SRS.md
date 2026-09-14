> Source of truth: `MintHRM_SRS_Report_Builder.docx`. This Markdown mirror is for in-repo reference (Architecture §8.3).

MintHRM

Human Resource Management Platform

Software Requirements Specification (SRS)

AI-Assisted Self-Service Report Builder

Prepared for: Technical Head – Approval & Sign-off

Document type: SRS / Business Analysis

Version: 0.2 (Draft for review)

Status: Pending approval

Confidential – Internal use only


# Document Control

Field

Detail

Document title

SRS – AI-Assisted Self-Service Report Builder

Product

MintHRM (multi-tenant HR SaaS)

Author

Product / Business Analysis

Reviewer / Approver

Technical Head

Version

0.2 (Draft for review)

Date

2026


### Revision history

Version

Date

Author

Summary of change

0.1

2026

BA / Product

Initial draft for Technical Head approval

0.2

2026

BA / Product

Added chat-only report building path and Template Versioning & Lifecycle section, following Technical Head review


# Table of Contents


# 1. Introduction


## 1.1 Purpose

This document specifies the requirements for a new module within the MintHRM platform: an AI-Assisted Self-Service Report Builder. The objective is to allow a client’s HR staff — or MintHRM support staff acting on a client’s behalf — to design, configure, preview and publish custom reports from the client’s HR data without any involvement from a developer, database administrator, or report-writing specialist.

This document is intended to give the Technical Head the information required to evaluate and approve the proposed approach, architecture, and scope before detailed design and development begin.


## 1.2 Scope

In scope: A web-based report builder (admin panel) and a separate report viewer panel, a semantic/metadata layer over the existing PostgreSQL datamart, an AI assistant to accelerate report creation, a safe query engine, export to Excel and PDF, report scheduling, and role-based access.

Out of scope (this phase): changes to the upstream ETL that populates the datamart, dashboarding/BI visualisations beyond tabular and basic grouped reports, and mobile-native applications. These are noted in Section 11.


## 1.3 Definitions & glossary

Term

Meaning

Datamart

The existing PostgreSQL store holding processed HR data for ~200 clients, separated per client by schema.

Tenant / Client

A single customer organisation. Each has its own schema in the datamart.

Semantic layer

A metadata catalogue that maps business concepts (e.g. “Employee Name”) to physical tables/columns, including joins and measures.

Report definition

The saved specification of a report, stored as JSONB. Split into a data spec and a presentation spec.

Query engine

The deterministic backend component that compiles a report definition into safe, parameterised SQL.

PII

Personally Identifiable Information (e.g. names, NIC, salary, contact details).

ZDR

Zero Data Retention — an enterprise AI-provider arrangement under which prompts/outputs are not stored at rest.


# 2. Business Context & Problem Statement

MintHRM currently operates a data warehouse and a per-client datamart in PostgreSQL. Processed HR data for approximately 200 clients is held in the same database, separated into per-client schemas. Today, when a client needs a custom report, the request must be handled manually by a developer who writes SQL and formats the output.


## 2.1 Problems with the current process

Every custom report depends on developer availability, which creates a bottleneck and slows client delivery.

Report logic lives in ad-hoc scripts rather than a reusable, governed definition.

Clients cannot self-serve, so even small changes (a new filter, a different column order) require a support ticket.

There is no consistent, branded output format (header/footer/logo) or standard export experience across clients.


## 2.2 Business goals

Enable non-technical users (client HR or MintHRM support) to build reports independently.

Reduce developer involvement in report delivery to effectively zero for standard cases.

Provide professional, branded, exportable output (Excel and PDF).

Maintain strict data isolation and privacy across the 200 tenants, including for any AI features.


# 3. Proposed Solution Overview

The solution introduces a layered architecture that sits on top of the existing datamart. Rather than letting users (or an AI) touch raw database tables directly, all report building happens against a governed semantic layer. A deterministic query engine — never the AI — is the only component that generates and runs SQL against the data.

Report creation is accelerated by an AI assistant that accepts two interleavable input modes within a single session: natural-language report requests (chat) and sample Excel uploads. Either can be used alone, and the two can be mixed in any order — for example, starting in chat and dropping in an Excel sample to refine the layout, or starting from an Excel and adjusting by chat. Crucially, the AI operates only on metadata and the report specification — it never receives actual employee records. This is the central privacy guarantee of the design and is detailed in Section 8.

Two separate panels are delivered:

Builder panel (MintHRM support / client HR admin) — design and publish report templates.

Viewer panel (client end-users) — run published reports, apply filters, and download Excel/PDF.


## 3.1 End-to-end flow for a non-technical user

Open the Builder panel and select the target client/tenant.

Build the report using the AI assistant in either input mode — describe it in plain language and/or upload a sample Excel — mixing the two freely as needed.

The AI proposes the report fields from the semantic layer; the user confirms or adjusts each one, and may keep refining by chat or by dropping in an Excel sample at any point.

The user configures filters using the filter panel (date ranges, dropdowns, multi-select, comparison operators).

The user customises header, footer, logo, and column formatting, then previews the report live.

The user saves the template (stored as JSONB — data spec + presentation spec).

Client end-users open the Viewer panel, run the report, and download it as Excel or PDF.


# 4. System Architecture

The system is organised into seven logical layers. Each layer has a single responsibility, which keeps the AI isolated from raw data and keeps SQL generation deterministic and safe.

#

Layer

Responsibility

1

Data source

Existing PostgreSQL datamart, accessed via a read-only replica and a read-only DB user. Reporting load never hits the production primary.

2

Semantic layer

Metadata catalogue mapping business concepts to physical tables/columns per tenant; defines dimensions, measures, joins and relationships.

3

Query engine

Compiles a structured report definition into parameterised, tenant-scoped SQL with row limits and timeouts. The ONLY component that issues SQL.

4

Report definition store

JSONB storage of report templates, split into a data spec (fields, filters, aggregation) and a presentation spec (layout, branding, formatting).

5

AI assistant

Excel-layout interpretation, natural-language report requests, and chat-based refinement — all operating on metadata and specs only, never on PII.

6

Rendering engine

Produces branded Excel and PDF outputs (header/footer/logo, column formats, conditional formatting).

7

Presentation panels

Builder panel (design/publish) and Viewer panel (run/download), plus scheduling and audit logging.


## 4.1 Why a semantic layer (key design decision)

Across 200 tenants the physical schema varies (e.g. employee data may live in tables named differently per client). Letting an AI guess the meaning of raw columns is unreliable and letting it write raw SQL is a security risk. The semantic layer solves both: it is a one-time, tech-team-managed mapping of physical schema to clean business concepts. After it exists, both the AI and the visual builder work against business-friendly names, which makes AI suggestions reliable and SQL generation safe and deterministic.

What the semantic layer defines: entities (Employee, Department, Leave, Attendance, Payroll), dimensions and measures (e.g. “Employee Name”, “Leave Balance”, “Total Salary”) and which column each maps to, predefined joins/relationships, and per-tenant schema mapping (auto-introspected, then manually enriched).


## 4.2 Why the AI never writes SQL

The AI produces a structured query specification (a JSON object listing fields, filters, grouping and sorting). The query engine — not the AI — converts that specification into SQL. The SQL is always parameterised, constrained to the current tenant’s schema, and guarded with a row limit and a statement timeout. This prevents cross-tenant data leakage, SQL injection, and accidental writes, none of which can be reliably guaranteed if an AI emits raw SQL strings.


# 5. Functional Requirements


## 5.1 Report Builder (Admin Panel)

The builder is the core authoring experience. It must provide, at minimum:

ID

Requirement

FR-B1

Field selector with drag-and-drop to add/remove/reorder report columns from the semantic layer.

FR-B2

Strong filter panel supporting date ranges, single-select and multi-select dropdowns, free-text match, and comparison operators (=, ≠, >, <, ≥, ≤, between, contains, is null).

FR-B3

Grouping and aggregation (sum, average, count, min, max) with sub-totals and grand totals.

FR-B4

Sorting on one or more columns (ascending/descending).

FR-B5

Calculated/derived fields built from existing measures (e.g. net = gross − deductions).

FR-B6

Column-level formatting: date format, number/decimal, currency, percentage, alignment, width.

FR-B7

Conditional formatting (e.g. highlight values above/below a threshold).

FR-B8

Header / footer / logo customisation per template (and per-tenant branding defaults).

FR-B9

Live preview of the report as it will be exported, on a limited sample of rows.

FR-B10

Save report as a reusable template; support template versioning and rollback.

FR-B11

Export to Excel (.xlsx) and PDF with branding and formatting preserved.


## 5.2 AI Assistant

Chat and Excel are two equal input modes within a single authoring session, not separate entry points. The client may choose whichever they prefer, and the two can be interleaved freely in any order at any point in the same session.

All of the following must be supported as first-class flows:

Chat-only: build a complete report from scratch by describing it in plain language, with no Excel involved.

Excel-only: upload a sample layout, confirm the suggested mapping, and save.

Excel-then-chat: start from an uploaded sample, then refine it through chat (add/remove columns, change filters, grouping).

Chat-then-Excel: start a report in chat, then drop in a sample Excel mid-session to help capture or refine the layout/columns.

An uploaded Excel is therefore a piece of context that can be introduced at any moment in the session, not a mandatory first step. Regardless of how the session unfolds, it resolves into the same report definition.

ID

Requirement

FR-A1

Sample Excel upload (any point in a session): parse the uploaded sheet’s header row and layout, and propose a mapping of each column to a semantic-layer field. The user must confirm or correct each mapping before it is applied (human-in-the-loop).

FR-A2

The system must strip all data rows from any uploaded Excel before any AI call. Only column headers and locally-inferred data types are sent to the AI (see Section 8).

FR-A3

Natural-language request: the user describes a report in plain language; the AI returns a structured query specification against the semantic layer. This mode requires no Excel and must support building a full report from scratch.

FR-A4

Adjustment chat: the user refines an existing report by instruction (e.g. “remove this column”, “group by department”, “only employees who joined in the last 3 months”); the AI returns an updated specification. This works whether the report was started from Excel or from chat.

FR-A5

Mode interleaving: within one session the user may switch between chat and Excel input freely and repeatedly; later input refines the same working report rather than starting a new one.

FR-A6

All AI output is a specification or a mapping suggestion only. The AI never returns SQL and never receives row-level data.

FR-A7

Both input modes converge on the identical JSONB report definition, so downstream behaviour (preview, export, scheduling, versioning) is the same regardless of how the report was created.


## 5.3 Filter Panel (runtime)

In the Viewer panel, end-users must be able to apply the filters that the builder enabled for a report, without editing the template. Filter values entered at runtime are passed as parameters to the query engine, never concatenated into SQL.


## 5.4 Report Viewer (User Panel)

ID

Requirement

FR-V1

List of published reports available to the logged-in user, scoped to their tenant and role.

FR-V2

Run a report, apply enabled runtime filters, and view results in a paginated table.

FR-V3

Download the report as Excel or PDF.

FR-V4

Users cannot edit template definitions from the Viewer panel.


## 5.5 Scheduling & delivery

Beyond on-demand running, the system should support scheduled reports (e.g. “run on the 1st of every month and email the PDF/Excel to a recipient list”). Scheduling is a common expectation for a SaaS report builder and reduces repetitive manual work for clients.


## 5.6 Audit logging

Because the data is HR/PII, the system must record who ran or exported which report and when, and who created or modified each template. This supports client compliance obligations and internal traceability.


# 6. Report Definition Model (JSONB)

Each report template is stored as JSONB and deliberately split into two parts so that presentation can change without rebuilding the query, and vice-versa.

Spec

Contains

Purpose

Data spec

Selected fields, filters, aggregations, grouping, sorting, calculated fields.

Drives the query engine to fetch the correct data.

Presentation spec

Column order, labels, formats, conditional formatting, header/footer/logo, page setup.

Drives the rendering engine for Excel/PDF and the on-screen preview.

Report definitions are stored per tenant. The AI chat history used for adjustments is associated with the draft template, not with any underlying data records.


# 7. Template Versioning & Lifecycle

Report templates change over time, so the system must version them safely. The key design clarification below was confirmed during Technical Head review.


## 7.1 Source of truth: the report definition, not the SQL

The canonical, version-controlled artifact is the report definition (data spec + presentation spec). The SQL is a compiled artifact derived from the data spec and the semantic layer; it is not hand-edited and is not an independent source of truth. When a user changes a report, they change the specification, and the SQL is regenerated from it. SQL is therefore never edited directly — doing so would let the SQL and the specification drift apart, after which the SQL would no longer match the spec. Storing the generated SQL is acceptable as a cache/snapshot, but it is always reproducible from the definition.


## 7.2 Versioning model

Immutable version snapshots: each saved version captures the full template (both the data spec and the presentation spec together), because correctness depends on their combination, not either part alone.

Draft vs published: a working draft is separated from the published version. The Viewer panel always runs the latest published version, so editing a draft does not affect end-users until it is published.

Rollback: any previous version can be re-published. Because history is retained, “restore the previous version” is always available.


## 7.3 Semantic-layer pinning

Each version is generated against a specific version of the semantic layer, and that reference is stored in the version snapshot. If the underlying schema mapping later changes, older template versions do not silently break: the stored pin allows the SQL to be regenerated correctly for the version that was saved.


## 7.4 Chat history

Chat history is a build-time aid and an audit trail. It is associated with the draft/version and written to the audit log (who built the report and with what instructions), but it is not part of the runtime artifact. When a report is run, the chat history is not used.


## 7.5 Open decision – versioning trigger

A decision is requested on when a new immutable version is created: on every save, or only when the user explicitly publishes. Recommendation: autosave the draft continuously but create a version snapshot only on explicit publish. This keeps history clean and avoids accumulating junk versions while still preserving full rollback capability.


# 8. AI Usage & Data Privacy (PII Protection)

This section directly addresses the concern of whether PII could be exposed to an AI model. It is the most important non-functional consideration in the design.


## 8.1 Core principle: the AI never receives PII

The protection does not depend primarily on whether the AI model is external (e.g. a hosted API) or self-hosted. The primary control is architectural: the AI only ever sees metadata and specifications, never actual employee records. The AI’s three tasks require only the following inputs:

Excel mapping: column header names and locally-inferred data types — with all data rows removed before the call.

Natural-language request: the user’s typed request plus the semantic layer’s business field names.

Adjustment chat: the current report specification (field names, filters) — not query results.

Actual data is fetched and rendered exclusively by the deterministic query and rendering engines, which never call the AI. Therefore no employee names, salaries, NIC numbers, or contact details flow to the AI under any of the three features.


## 8.2 Mandatory safeguard for Excel upload

Because an uploaded sample sheet could contain real data, the system must, before any AI call: (a) read only the header row, (b) infer column data types locally using a Python library (e.g. pandas) rather than asking the AI, and (c) discard all data rows. The user-facing upload instruction should explicitly ask clients to provide a layout sample with dummy or no data.


## 8.3 External API vs self-hosted model

With the metadata-only architecture in place, an external AI provider API is acceptable for this use case, provided enterprise data terms are used. For reference, current provider terms indicate that data sent to the Anthropic API is not used for model training, standard API log retention is short (7 days by default, configurable), and a Zero Data Retention (ZDR) arrangement plus a HIPAA-style Business Associate Agreement (BAA) are available for enterprise customers. Equivalent enterprise/API terms exist for other major providers. (These terms should be verified with the chosen provider at contract time.)

A self-hosted open-weight model (e.g. Llama or Mistral on company GPUs) remains an option, but it is recommended as a configurable choice for clients with strict data-residency contracts rather than as the default, because self-hosted models are generally weaker, carry GPU and maintenance cost, and add operational burden.


## 8.4 Recommended three-tier privacy stance

Tier

Control

Notes

1 – Architectural (primary)

AI sees metadata and specs only; never row-level PII.

Must hold true for both external and self-hosted models. This is the real protection.

2 – Default deployment

External API under ZDR + BAA, no training on customer data.

Best capability, lowest infra cost; suitable for HR data when PII is excluded by design.

3 – Optional

Self-hosted open-weight model on MintHRM infrastructure.

Offered to clients whose contracts forbid any data leaving controlled infrastructure.


# 9. User Roles & Permissions

Role

Panel

Capabilities

MintHRM Support / Admin

Builder

Create/edit/publish templates for any tenant; manage semantic layer; full audit visibility.

Client HR Admin

Builder (own tenant)

Create/edit/publish templates within their own tenant; manage branding.

Client End-User

Viewer

Run published reports, apply runtime filters, download Excel/PDF (own tenant only).

System / Tech team

Backend

Manage semantic-layer mappings, replica access, and AI configuration.

All access is tenant-scoped. A user can never run, view, or build a report against another tenant’s schema; this is enforced by the query engine, not by UI alone.


# 10. Data Flow Summary


## 10.1 Build-time flow

User input (Excel headers / NL request) → AI assistant → proposed specification.

User confirms/adjusts → specification finalised against semantic layer.

Template (data spec + presentation spec) saved as JSONB.


## 10.2 Run-time flow

User opens a published report and sets runtime filter values.

Query engine compiles the data spec + filter parameters → tenant-scoped parameterised SQL.

SQL runs on the read-only replica; results returned (row-limited, timed-out).

Rendering engine applies the presentation spec → Excel/PDF output.

Action recorded in the audit log.

Privacy note: the AI participates only in step 1–2 of the build-time flow. It is entirely absent from the run-time flow where real data is processed.


# 11. Non-Functional Requirements

ID

Category

Requirement

NFR-1

Security / Isolation

Strict per-tenant data isolation enforced at the query-engine level; read-only DB access; parameterised SQL only.

NFR-2

Privacy

No PII transmitted to any AI component; ZDR + BAA for external AI; audit log for all report runs/exports.

NFR-3

Performance

Reporting runs on a read replica; row limits and statement timeouts on every query; preview limited to a sample.

NFR-4

Scalability

Architecture must support ~200 tenants and growth; semantic layer and definitions stored per tenant.

NFR-5

Usability

A non-technical user can build and publish a report end-to-end with no SQL, DB, or developer involvement.

NFR-6

Reliability

Scheduled report failures are logged and retried; users are notified of failed deliveries.

NFR-7

Auditability

All template changes and report executions are attributable to a user and timestamped.

NFR-8

Maintainability

Report logic lives in governed definitions (JSONB) and the semantic layer, not ad-hoc scripts.


# 12. Assumptions, Dependencies & Out of Scope


## 12.1 Assumptions

The existing datamart is well-formed enough to be introspected and mapped into a semantic layer.

A read replica of the datamart can be provisioned for reporting load.

Clients can provide a sample Excel layout (with dummy or no data) when desired.


## 12.2 Dependencies

Availability of an enterprise AI provider contract (ZDR + BAA) or self-hosted model infrastructure.

Tech-team effort for the one-time semantic-layer setup per tenant.


## 12.3 Out of scope (this phase)

Changes to upstream ETL/data warehouse pipelines.

Advanced BI dashboards and charts beyond tabular and grouped reports.

Native mobile applications.


# 13. Indicative Technology Stack

Provided for discussion; the final stack is subject to the Technical Head’s direction.

Concern

Indicative choice

Database / source

PostgreSQL (existing) + read replica

Backend / query engine

Python (deterministic SQL builder; parameterised queries)

Excel rendering

openpyxl / XlsxWriter

PDF rendering

WeasyPrint or ReportLab

Excel parsing (upload)

pandas (headers + type inference; data rows stripped)

AI assistant

External enterprise API under ZDR + BAA (default) or self-hosted open-weight model (optional)

Report definition store

PostgreSQL JSONB


# 14. Approval & Open Decisions

The following decisions are requested from the Technical Head before detailed design proceeds:

Approval of the semantic-layer approach as the foundation (vs. direct schema access).

Approval that the AI must never receive PII and must never emit SQL (architectural constraint).

Decision on default AI deployment: external API (ZDR + BAA) vs self-hosted, or a per-client configurable model.

Approval of the two-panel (Builder / Viewer) model with scheduling and audit logging.

Sign-off

Role

Name

Signature

Date

Technical Head

Author / BA
