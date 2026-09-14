# Semantic Layer — Architecture Review & Comparison

> **Scope:** This document reviews the semantic layer of **Mint-Report-Builder** and
> compares it against the semantic layer of **mint-analytics** (the finance-intelligence
> platform). It is intentionally limited to the *semantic layer* only — query execution,
> rendering, export, and UI are out of scope.
>
> **Date:** 2026-06-11 · **Reviewer:** Architecture review (Claude) · **Audience:** Tech lead + team

---

## 1. TL;DR

The two projects implement **two genuinely different architectural philosophies** of a
"semantic layer" — not two variations of one design.

| | **mint-analytics (Tech Lead)** | **Mint-Report-Builder (this project)** |
|---|---|---|
| What the semantic layer *is* | Physical **SQL views** (`vw_*`) in PostgreSQL | An application-level **metadata catalog** (JSONB / Pydantic) |
| Where it lives | In the database (dbt SQL files) | In Python code + a JSONB column per tenant |
| Industry pattern name | **"Curated views" / DB-centric** | **"Headless BI / metrics layer"** (Cube.dev, LookML, dbt Semantic Layer, Malloy) |
| Security boundary | **Database role** (`ai_reader` granted only `vw_*`) | **Application guards** (read-only user + read-only txn + SELECT-only assertion) |
| Multi-tenancy | Single tenant | **Multi-tenant**, per-tenant catalog, zero-touch bootstrap |
| Versioning | `rules_sha` on every mart row | **`semantic_version_ref`** pinned on every report version |
| Flexibility | Fixed, curated reports | **Arbitrary user-built reports**, compiled at runtime |
| AI involvement | Deterministic, no runtime LLM | LLM produces a **validated spec** (never SQL, never sees data/PII) |

**Verdict:** As a *semantic layer in the textbook sense*, this project's design is **more
sophisticated and more modern**. The difference is largely driven by a different product
requirement — a **self-service report builder** *requires* a flexible catalog (you cannot
pre-build a view for every possible report), whereas a fixed finance-reporting product is
well served by curated views. Both are fit-for-purpose; neither is simply "better."

---

## 2. Why the designs differ — the product requirement

- **mint-analytics** ships a fixed set of finance reports (P&L, Balance Sheet, Trial
  Balance, Cash Flow) plus an AI Q&A surface over them. A small number of **curated
  views** is the natural, simplest fit.

- **Mint-Report-Builder** lets a **non-technical HR admin design *any* custom report** by
  chat, Excel upload, or manual field selection. You cannot hand-author a view per report,
  so the semantic layer must be a **flexible metadata abstraction** that compiles to SQL at
  query time.

> Analogy: the tech lead's layer is a restaurant with a **fixed menu** (10 chef-prepared
> dishes). This project's layer is a **pantry of ingredients (refs) + recipes (joins)**
> from which the user composes any dish, assembled to order at runtime.

---

## 3. This project's semantic layer — how it actually works

### 3.1 The core model (`app/domain/semantic.py`)

```
SemanticCatalog (per tenant, versioned, stored as JSONB)
├── entities: [ Entity ]
│   ├── name / key / base_schema / base_table / primary_key
│   ├── period_grain (optional)  ← drives period-aligned joins
│   └── fields: [ SemanticField ]
│       ├── ref        "employee.full_name"   ← the ONLY thing the AI sees
│       ├── label / type / role / allowed_aggregations / pii
│       └── physical: PhysicalColumn(table, column, schema)  ← NEVER exposed to AI
└── joins: [ JoinDef ]   ← the Query Engine only ever composes DECLARED joins
```

- A `ref` is a stable business key of the form `<entity>.<field>`. **Physical names live
  ONLY in `PhysicalColumn`.** Nothing outside the semantic layer knows physical table or
  column names.
- `metadata_for_ai()` is the **only** projection handed to the AI — `ref / label / type /
  role / entity / allowed_aggregations`. No physical names, no data, no PII.

### 3.2 End-to-end flow

```
User: "active employees by department, total basic salary"
        │
        ▼
[AI Adapter] ── sees only catalog.metadata_for_ai()  (no physical names, no data, no PII)
        │  returns a DataSpec (structured JSON) — NEVER raw SQL
        ▼
[AIService._validate] ── Pydantic DataSpec + guards.validate_refs + guards.validate_joins
        │  (the AI's JSON is never trusted raw)
        ▼
[Query Engine compiler] ── refs → physical via SemanticCatalog.resolve()
        │  builds a SQLAlchemy Core Select (parameterized, no string concat)
        │  + period-grain join alignment
        ▼
[Guards] ── assert_select_only + row-limit + declared-joins-only
        │
        ▼
[Runner] ── read-only DB user + read-only transaction + search_path locked to the tenant
```

### 3.3 Lifecycle features worth calling out

- **Zero-touch bootstrap** (`get_active_catalog`): a tenant's first request auto-assembles a
  catalog (curated seed + the tenant's own dynamically-introspected paysheet pay items).
- **Version pinning** (`get_pinned_catalog`): every report records the exact
  `semantic_version_ref` it was built against, so old reports reproduce correctly after a
  mapping change.
- **Change-aware refresh** (`refresh_if_changed`): a nightly job re-introspects and bumps
  the version *only if the field set changed* — no accumulation of identical versions.
- **Live introspection** (`introspect_datamart`, `_introspect_paysheet`,
  `_introspect_summary_marts`): proposes entities/fields from `information_schema` and the
  governed `vw_data_dictionary` (business descriptions + authoritative PII flags).

---

## 4. Strengths (PLUS)

1. **Modern headless-BI architecture.** Business `ref`s are fully decoupled from physical
   columns. If a mart changes, you update the catalog's physical mapping only — reports do
   not break. (The view-based approach needs a dbt/DBA change to alter a view.)

2. **Version pinning (`semantic_version_ref`) — excellent.** Equivalent in spirit to the
   tech lead's `rules_sha` lineage, applied to the *mapping* layer. Old reports stay
   reproducible after the catalog evolves. Same maturity level.

3. **Multi-tenant + zero-touch onboarding.** A new SaaS tenant is provisioned and its
   catalog assembled on first access. A clear advantage over the single-tenant view design.

4. **The AI never sees data, physical names, or PII.** `metadata_for_ai()` is the only shape
   the AI receives. The AI returns a **validated `DataSpec`, never SQL** — strong security
   posture.

5. **Defense-in-depth for read-only access (3 independent layers)** in `query_engine/guards.py`:
   read-only DB user → read-only transaction → `assert_select_only` (forbidden-keyword +
   single-statement check). Well-considered.

6. **Auto-introspection of dynamic content.** Per-tenant paysheet pay items
   (additions/deductions vary by tenant) are introspected rather than hand-coded.

7. **Period-grain join alignment** (`compiler.py`, `_apply_joins`). A subtle but deep piece:
   joining two period-grained marts on employee alone would cross-multiply rows across
   periods; the compiler additionally matches on `(year, month)` to collapse the product back
   to one row per employee per period. Prevents a whole class of silent data bugs.

8. **Cost-aware AI usage.** Excel/label mapping is fuzzy-match-first; only *ambiguous*
   headers are batched to the AI, and a dominant-cluster pass guarantees a single joinable
   entity set. Scales to wide paysheets and small-context models.

---

## 5. Concerns (MINUS) & recommendations

| # | Concern | Where | Severity | Recommendation |
|---|---------|-------|----------|----------------|
| 1 | **Security is enforced in the app layer, not the DB.** If a guard is bypassed or the compiler has a bug, raw data could leak. The view-based design is harder to bypass because the DB role itself blocks raw access. | `query_engine/guards.py`, `db/datamart.py` | **High** | Add a **DB-level read-only role + per-tenant grants** (mirror the tech lead's `ai_reader`). Keep the app guards *and* the DB role — belt **and** braces. |
| 2 | **`eval()` for calculated-field expressions.** Guarded by a tokenizer that allows only refs, numbers, parentheses and the four arithmetic operators, so it is reasonably safe — but it is still `eval`. | `compiler.py` `_parse_calc` (`# noqa: S307`) | Medium | Replace with an **AST-based evaluator** (`ast.parse` + a node whitelist) for a 100% non-`eval` guarantee. |
| 3 | **LLM dependency at build time.** Real LLM (Anthropic) is used to produce the spec. Output is clamped by the `DataSpec` + guards, but the same prompt may not yield the same spec (non-deterministic), plus cost/latency. | `services/ai_service.py`, `ai/` | Low–Medium | This is fine: the LLM runs at **build** time (human-reviewed) and **never** at report *run* time (the compiler is deterministic). Keep that boundary explicit and documented. |
| 4 | **Heuristic role inference.** Introspection treats numeric columns as measures (with a `_DIM_NUMERIC` exception list). A new dimension-numeric column (e.g. `grade_level`, `cost_center_code`) could be misclassified as a measure. | `semantic_service.py` `_introspect_*` | Medium | Prefer an explicit `role` column in `vw_data_dictionary` over inference; fall back to the heuristic only when absent. |
| 5 | **Naming-convention coupling.** `vw_`/`mart_`/`dim_` prefixes, `_sk` suffix, and `payroll_year/month` names are hard-coded; a datamart convention change breaks introspection silently. | `semantic_service.py`, `compiler.py` | Low–Medium | Lift conventions into config/constants and document them as a datamart contract. |
| 6 | **Broad `except Exception` (`# noqa: BLE001`) in several introspection paths.** Fault-tolerance (VPN down → seed-only) is the right intent, but a real bug (e.g. a SQL typo) can be swallowed as "datamart unreachable." | `semantic_service.py` | Low | Catch specific exception types where possible; always log the full traceback so genuine failures are visible. |

---

## 6. Side-by-side summary

| Dimension | mint-analytics (views) | Mint-Report-Builder (catalog) |
|---|---|---|
| Semantic layer form | SQL views in DB | Metadata catalog (JSONB) |
| Flexibility | Fixed curated reports | Arbitrary runtime-compiled reports |
| Security enforcement | **DB role** (strongest) | App guards + read-only user/txn |
| Multi-tenant | No | **Yes** (zero-touch) |
| Reproducibility | `rules_sha` on rows | **`semantic_version_ref`** pinned per report |
| AI | Deterministic, no LLM | LLM → validated spec (no SQL, no PII) |
| Maintenance to add a field | dbt model + DBA | Catalog update / auto-introspection |
| Complexity | Lower | Higher (compiler, joins, versioning) |
| Best fit | Fixed finance reporting + Q&A | Self-service HR report building |

---

## 7. Bottom line

- As a **semantic layer in the industry sense**, this project's design is the more advanced
  and more modern of the two — it is the headless/metrics-layer pattern (LookML / Cube /
  dbt Semantic Layer), with multi-tenancy, version pinning, period-grain join alignment, and
  a clean AI-never-sees-data boundary.
- The tech lead's view-based design is **simpler and DB-security-enforced**, and is the right
  fit for fixed, curated finance reporting.
- The single highest-value change for this project: **add a DB-level read-only role + per-tenant
  grants** (adopt the tech lead's `ai_reader` pattern) so security no longer rests solely on
  application correctness. With app guards *and* a DB role, this semantic layer is
  architecturally hard to beat.

---

### Key files (this project)

- `backend/app/domain/semantic.py` — catalog/entity/field/join model + AI metadata projection
- `backend/app/services/semantic_service.py` — catalog resolution, bootstrap, introspection, versioning
- `backend/app/query_engine/compiler.py` — spec → safe SQLAlchemy `Select` (refs, joins, calc fields, unpivot)
- `backend/app/query_engine/guards.py` — refs/joins validation, row-limit, SELECT-only assertion
- `backend/app/services/ai_service.py` — AI orchestration; validates every AI output against the catalog
- `backend/app/repositories/semantic_repo.py` — per-tenant catalog persistence (versioned)
</content>
</invoke>
