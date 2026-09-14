# Semantic Layer — Comparison Review

**Mint Report Builder** (this project) vs **mint-analytics** (tech-lead reference)

> Purpose: a clear, honest, side-by-side review of how each project models its
> "semantic layer" — the metadata tier that maps business concepts to physical
> data — so we understand where they agree, where they diverge, and *why* each
> made the choices it did. Both are correct **for their own product**; the
> differences are not "better/worse" but "different problem shapes".

_Last reviewed: 2026-06 · grounded in code inspection of both repos._

---

## 1. TL;DR — the one-line difference

|                | **Mint Report Builder (ours)**                          | **mint-analytics (tech lead)**                                |
| -------------- | ------------------------------------------------------- | ------------------------------------------------------------- |
| **In a phrase**| A **dynamic, per-tenant, AI-assisted** catalogue that *discovers* each client's data shape | A **curated, hand-authored, deterministic** rule-book for one regulated finance domain |
| **North star** | Flexibility & self-service across many tenants          | Correctness & auditability for standardized financial reports |
| **Authored by**| The system (auto-introspection) + end users (custom metrics) | Domain experts, in git-reviewed YAML                          |
| **Domain**     | Domain-neutral (HR / payroll / generic documents)       | Insurance & general-ledger finance                            |
| **AI**         | LLM **in the loop** (tiered: deterministic → LLM)       | **No LLM** — rule-based intent classifier                     |

**The essence:** theirs is a *closed, governed, expert-curated* semantic layer for a
fixed set of reports in one domain. Ours is an *open, dynamic, multi-tenant*
semantic layer that adapts itself to whatever each client's datamart contains.

---

## 2. Side-by-side matrix

| Dimension | Ours (Mint Report Builder) | Theirs (mint-analytics) |
|---|---|---|
| **Definition format** | Python **Pydantic models** → **JSONB** in Postgres | Hand-authored **YAML** files in git |
| **Source of truth** | DB (per-tenant catalogue rows) | Code/YAML under `app/rules/` (git SHA = audit) |
| **Authoring** | Auto-introspected + seed + user-defined | Manual, PR-reviewed by experts |
| **Multi-tenancy** | **True per-tenant catalogue** (one versioned model each) | **Per-schema data isolation**; rules are **global/shared** |
| **Adapts to per-tenant schema?** | ✅ Yes — discovers each client's pay items dynamically | ❌ No — same YAML for everyone; new field = code change |
| **Metrics** | `MetricDef` (aggregate / count / formula), **validated-on-define**, **user-creatable** | 27 canonical metrics in YAML, rich domain semantics, expert-authored |
| **Glossary / business terms** | ✅ Built (per-tenant `semantic_glossary`, validated-on-define, feeds resolver) | ✅ `finance_glossary.yaml` (term → definition → metric) |
| **Joins** | Declared `JoinDef` + **period-grain alignment** | Implicit **star schema** (dbt fact + dim tables) |
| **Materialization** | ❌ None (queries hit live datamart) | ✅ dbt **fact/dim tables** + AI-safe views |
| **AI / NL → query** | LLM (tiered with deterministic resolver) | Deterministic rule-based classifier (no LLM) |
| **PII handling** | `pii` flag; stripped before AI; *not* masked in results | (finance — less PII-centric); ledger views only |
| **Row-level security (within a tenant)** | ❌ Not built (tenant isolation only) | ✅ External-API-driven `data_access_rules` |
| **Governance engine** | Validate-on-define + guards (refs/joins/SELECT-only) | **Constitutional invariants** engine (13 invariants, OBSERVE/WARN/BLOCK) |
| **Versioning** | Integer version per tenant, **pinned to reports** | Git `rules_sha` stamped on every mart row |
| **Report definitions** | Fully **user-built** ad-hoc specs | **Fixed mappings** (pl001, bs001, cf001 …) |
| **Provisioning** | **Zero-touch** on first tenant access | Schema-clone per org |

---

## 3. Deep dive — where they actually differ

### 3.1 Definition & storage — *discovered* vs *authored*

**Ours** ([semantic.py](backend/app/domain/semantic.py), [semantic_service.py](backend/app/services/semantic_service.py)):
the catalogue is a `SemanticCatalog` Pydantic object — `entities[]`, `joins[]`,
`metrics[]` — persisted as JSONB per `(tenant_id, version)`. A curated **seed**
(Employee, Payroll, Leave …) is merged with **auto-introspected** dynamic entities
(every pay-item column read live from `mart_horizontal_paysheet_dynamic`). It is
*assembled at runtime* and saved; if the datamart is unreachable it falls back to
seed-only.

**Theirs** (`app/rules/semantic/*.yaml`): the semantic layer **is** a set of
hand-written YAML files, versioned in git. `metrics.yaml` (27 metrics),
`dimension_registry.yaml` (12 dimensions), `finance_glossary.yaml`. Every ETL row
is stamped with the `rules_sha` (git SHA of the rules dir) — so the audit trail is
literally the git history.

> **Why the divergence:** ours serves *many tenants with different data shapes* — we
> can't hand-author one model, so we discover it. Theirs serves *one finance domain
> where the chart of accounts is fixed and regulated* — hand-authoring is a feature
> (expert review, deterministic, auditable), not a limitation.

### 3.2 Metrics — *flexible & self-serve* vs *rich & expert-curated*

**Ours** ([metrics_service.py](backend/app/services/metrics_service.py)): `MetricDef{key,
label, kind, agg, ref, distinct, expression, filters, aliases, source}`. Three kinds:
`aggregate`, `count`, `formula` (arithmetic over *other* metrics). The big property:
**users can define a metric at runtime**, and `define()` **validates it compiles**
against the live catalogue before storing it (`_assert_compiles`). Per-tenant.

**Theirs** (`metrics.yaml`): 27 canonical metrics with *far richer domain
semantics* — `account_filter` (GL codes), `sign_convention` (credit_positive),
`role` (direct_lever/derived), `good_direction`, `threshold_warning/error`,
`depends_on`. Example: `combined_ratio = loss_ratio + expense_ratio` with a warning
threshold at 1.0. But: adding/changing one requires a **git PR**.

> **Trade:** ours wins on *agility & multi-tenant self-service*; theirs wins on
> *semantic richness & governed correctness*. Their `sign_convention` / `threshold` /
> `role` fields are ideas worth borrowing into our `MetricDef`.

### 3.3 The glossary tier — *they had it first; we now have it too (per-tenant)*

`finance_glossary.yaml` maps business terms (Loss Ratio, GWP) → plain-language
definition → the metric that computes it → industry benchmark. It grounds both the
UI and the (rule-based) AI so language stays anchored in authoritative definitions.

**We built the equivalent** ([glossary_service.py](backend/app/services/glossary_service.py),
[GlossaryTerm](backend/app/domain/semantic.py)): a per-tenant `semantic_glossary`
table of `GlossaryTerm{term, aliases, definition, ref, category}`. Each term is
**validated-on-define** (its `ref` must resolve to a real `metric.<key>` or field),
and the catalogue loads them as **synonyms into the deterministic NL resolver** — so
"in-hand salary by branch" resolves onto the governed `metric.total_net`, grounded
rather than guessed. Improvement over theirs: theirs is one global YAML; **ours is
per-tenant**, so each client can add its own vocabulary.

### 3.4 Multi-tenancy — *the biggest architectural fork*

- **Ours:** every tenant gets its **own catalogue**, versioned, and reports **pin** the
  version they were built against — so an old report regenerates identically even
  after the model changes. Onboarding is **zero-touch**: first API call bootstraps a
  full working model.
- **Theirs:** **per-schema** isolation (`org_id` = Postgres schema), but the **semantic
  rules are global** — one `metrics.yaml` for all orgs. Data is isolated; *meaning* is
  shared.

> Ours is "many models, shared engine"; theirs is "one model, many data schemas". Ours
> is the right shape for a SaaS where **clients differ in their data** (different pay
> items per client). Theirs is right when **all tenants report on the same regulated
> chart of accounts**.

### 3.5 AI / NL → query — *LLM-assisted* vs *deterministic*

- **Ours** ([ai_service.py](backend/app/services/ai_service.py), [intent_resolver.py](backend/app/services/intent_resolver.py)):
  tiered — a **deterministic resolver** handles common requests (field/metric label +
  alias matching, no LLM); anything else falls back to the **LLM**, whose output is
  validated against the catalogue + guards. Handles *arbitrary* requests.
- **Theirs:** **no LLM at all**. A rule-based intent engine classifies into a fixed set
  (LOOKUP / REPORT / COMPARE / VARIANCE / GLOSSARY) and builds TopN SQL deterministically.

> Ours trades some determinism for *open-ended flexibility*; theirs trades flexibility
> for *total determinism & reproducibility* — appropriate for regulated finance.

### 3.6 Governance — *validate-on-use* vs *constitutional engine*

- **Ours:** governance = **guards** (refs exist, joins declared, SELECT-only,
  calculated-field AST with no `eval`) + **validate-on-define** for metrics + run
  lineage/checksums (the gap-closure work). Pragmatic, query-path-focused.
- **Theirs:** a formal **constitutional-invariants** engine — 13 ratified invariants with
  severities (CONSTITUTIONAL/CRITICAL/…), an enforcement policy (**OBSERVE → WARN →
  BLOCK**), and registry hashing. Much heavier governance ceremony.

> Theirs is enterprise/regulatory-grade governance; ours is lighter and faster to
> evolve. For a multi-tenant self-serve builder, heavy constitutional governance would
> likely be over-engineering — but the **OBSERVE/WARN/BLOCK** staged-enforcement idea
> is a clean pattern.

### 3.7 Row-level security — *a real gap on our side*

Theirs has `data_access_rules`: per-connection rules that call an **external module API**
to fetch the row values a given user may see, then rewrite SQL with `WHERE col IN (...)`
(cached per user). **We only isolate by tenant** — within a tenant, every authorized user
sees all rows. For HR data (one manager should see only their team), **within-tenant RLS
is a legitimate SaaS gap** for us.

---

## 4. What each does *better*

**Ours is stronger at:**
- ✅ **Multi-tenant by design** — per-tenant versioned catalogue, version-pinned reports.
- ✅ **Dynamic adaptation** — auto-discovers each client's pay items; no code change per tenant.
- ✅ **Self-service** — users define custom metrics (validated) and build ad-hoc reports.
- ✅ **AI-assisted NL** — arbitrary natural-language requests, not a fixed intent set.
- ✅ **Domain-neutral** — HR today, anything tomorrow (the "document" concept generalizes).

**Theirs is stronger at:**
- ✅ **Semantic richness** — metrics carry sign convention, thresholds, roles, dependencies.
- ✅ **Glossary** — authoritative business-term definitions feeding UI + AI.
- ✅ **Determinism & auditability** — git-versioned rules, `rules_sha` on every row, no LLM.
- ✅ **Materialization** — dbt fact/dim tables (fast, decoupled from a flaky source).
- ✅ **Within-tenant RLS** — external-API-driven row filtering.
- ✅ **Formal governance** — constitutional invariants with staged enforcement.

---

## 5. What we can borrow (prioritized)

| Idea from theirs | Value to us | Effort | Priority |
|---|---|---|---|
| ~~**Glossary tier**~~ | ✅ **Done** — per-tenant, validated-on-define, wired into the resolver | — | Closed |
| **Within-tenant RLS** (data-access rules) | Real SaaS/compliance gap (manager sees only their team) | Med–High | **High** |
| **Richer `MetricDef` fields** (unit already; add `good_direction`, `threshold`, `role`) | Better UX, governance signals | Low | Med |
| **Materialized summary marts** (dbt-style) for known-heavy reports | Pairs with the caching work; survives VPN flakiness | High | Med |
| **OBSERVE/WARN/BLOCK** staged enforcement for validation gates | Cleaner rollout of data-quality rules | Low | Low–Med |

> Note: we should **not** adopt the heavy constitutional-governance engine wholesale —
> it fits a single regulated finance product, not a flexible multi-tenant builder. Take
> the *patterns* (staged enforcement, glossary), not the ceremony.

---

## 6. Bottom line

Both teams built a semantic layer; they are **not the same kind of object**:

- **mint-analytics** = a *governed rule-book*. Hand-authored, deterministic,
  audit-first, single domain. The semantic layer is **the product's authority**.
- **Mint Report Builder** = a *self-describing catalogue*. Discovered per tenant,
  flexible, AI-assisted, domain-neutral. The semantic layer is **the product's adapter**.

Neither is "ahead" of the other — they optimize different axes. The honest read:
**our multi-tenant + dynamic-introspection + self-serve-metrics design is the harder
SaaS problem and we solve it well**; **their glossary, richer metric semantics, RLS,
and materialization are concrete ideas we can selectively adopt** without taking on
their governance weight.
