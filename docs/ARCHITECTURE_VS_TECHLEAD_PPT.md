# Mint HR OS Architecture (tech-lead PPT) vs. our implementation

Source: `docs/Mint HR OS Architecture.pptx` — the reference architecture our senior
tech lead asked us to align to. This note maps that concept to what we have built on
`feat/ai-report-builder`, then lists the gaps and the plan.

## The tech lead's core principle

> Different users asking the **same question in different ways must get the same
> answer.** That consistency is what earns trust in the data and the system. It is
> achievable only if the **semantic layer and the data capture are conceptually
> correct and complete.**

The PPT's architecture that delivers this:

- **Understand once, reuse forever** — the language model runs *only* at the
  meaning step; everything after is deterministic, cached, sub-second.
- A question decomposes into **five blocks**: **Subject (entity) · Measure ·
  Grouping · Filter · Time.**
- **Infinite phrasings → finite canonical intent** (slide 5, 12). A *learning
  store* collapses every phrasing to one canonical intent and replays it — coverage
  compounds, the system never re-derives.
- **Not** dynamic text-to-SQL (non-deterministic, unbounded latency, hard to
  govern). **Not** a library of frozen SQL (brittle). Instead: question → intent →
  semantic layer → business spec → deterministic compiler → SQL.

## Verdict

**The PPT's reference architecture is the architecture we already built (Concept 1).**
We are not on dynamic text-to-SQL. In places we exceed the PPT — even the *meaning*
step is mostly deterministic (no LLM), not just the compile step.

## What already matches ✅

| PPT concept | Our implementation | Status |
|---|---|---|
| LLM at meaning step only, then compile | `nl_hybrid.hybrid_resolve` (deterministic-first) + LLM fallback | ✅ exceeds — meaning step usually deterministic |
| Business specification (`spec.json`) | `DataSpec` (entity / fields / filters / group_by / aggregations) | ✅ |
| Deterministic compiler, no AI SQL | `compile_query` → SQLAlchemy + guards (`assert_select_only`) | ✅ |
| Governed semantic layer (terms→tables), versioned | per-tenant JSONB catalogue, versioned | ✅ |
| Finite governed vocabulary | Metrics tier + Glossary tier | ✅ |
| Sub-second, cached | Redis result cache (≈9 ms verified on repeat) | ✅ |
| Injection-safe / approved blocks | guards, read-only datamart role, AST evaluator (no `eval`) | ✅ |
| Deterministic > text-to-SQL (head-to-head) | the whole approach | ✅ |

## Gaps (what the PPT has that we don't yet)

### 🔴 Gap 1 — Canonical-intent / Learning store (slide 12, 16) — missing
No store that locks a resolved phrasing to a canonical spec and replays it. Our
glossary is manual synonyms only; there is no feedback loop. **This is the tech
lead's #1 point** — the consistency *guarantee* and "compounds over time" come from
here.

### 🔴 Gap 2 — Time / Period as a first-class block (slide 7–9) — missing
The 5-block grammar's **Time** block (`this month`, `YTD`, `current year`,
`last 12 months`) is not parsed; `_parse_filters` handles only status + tenure, and
`DataSpec` has no period block. Required-period-filter (period-grain governance) is
still pending.

### 🟠 Gap 3 — Routing consistency *guarantee* — partial
Verified consistent for counts/roll-ups (e.g. `active count` → 325 four ways;
`headcount by employment type` → 17/308 four ways). But ambiguous phrasings can
still diverge: "basic salary" → `payroll.basic` vs `employee.current_basic`; "leave
category" → wrongly `employee.category`. Same concept must not map to two fields.
Needs deterministic tie-break + canonical lock (pairs with Gap 1).

### 🟠 Gap 4 — Data-capture correctness — mart-level
The semantic layer is only as trustworthy as the marts. Observed: `Department` is
`0/325` non-null (`mart_employee_current.designation_department` empty). The mapping
is right; the data capture is not. Needs an ETL/mart coverage audit.

### 🟡 Gap 5 — Certified canonical mapping per concept — governance
A governed guarantee (+ confirmation) that a concept always maps to one physical
mapping. Metrics/glossary exist but "certified canonical mapping per concept" is not
yet enforced.

## Plan (priority order)

| # | Work | Why | Status |
|---|---|---|---|
| 1 | **Canonical-intent / Learning store** — resolved phrasing → canonical spec, persisted & replayed; chat hits this first | Gap 1 — consistency guarantee + trust (tech lead #1) | ✅ done |
| 2 | **Time/Period block** — parse `this month`/`YTD`/`last N months`/`current year`; symbolic spec, compiler-resolved | Gap 2 — completes the 5-block grammar | ✅ done |
| 3 | **Deterministic tie-break + concept lock** — ambiguous phrase → same-entity preference + canonical metric/field priority | Gap 3 — stop diverging routes | ✅ done |
| 4 | **Data-capture coverage audit** — report null/missing mart columns (e.g. department), escalate to ETL | Gap 4 — semantic-layer trust = mart trust | ✅ done |
| 5 | **Certified canonical mapping per concept** — concept→mapping governance + confirmation | Gap 5 | ✅ done |

### Done (1–3)
- **#1 Learning store** — `LearnedIntent` table + `LearningStore`; chat replays a saved
  spec for a normalised phrasing (`source="learned"`), re-validated against the live
  catalogue. Same question (any phrasing that normalises equal, any user) → same answer.
- **#2 Time block** — `_parse_period` emits SYMBOLIC `@period:` filters; the compiler's
  `resolve_period_value` ("current_period()") binds concrete year/month/date at run time,
  so a learned "this month" report never goes stale. Plus a filter-only fallback
  ("employees who joined in the last 12 months").
- **#3 Concept-lock** — deterministic `_rank_matches` (metric-first, then catalogue order)
  + entity-level re-pick, so "basic salary" resolves to the employee field in an employee
  report and the payroll field in a payroll report — reproducibly.

- **#4 Data-capture audit** — `CoverageAuditService` (POST `/validations/coverage`) walks
  every catalogue field and measures how populated its backing column is, one query per
  table — catalogue-driven, nothing hand-listed. Flags `empty` (0% populated, e.g.
  `employee.department` → `designation_department`) and `missing` (column dropped) fields,
  persisting them as `completeness` validation results. On demo_tenant it surfaced 9 empty
  fields automatically.

- **#5 Certified canonical mapping** — `LearningStore` governance + `/learning` router:
  an HR admin can list learned intents and CERTIFY one as the authoritative answer for a
  question (locked from being overwritten by re-resolution), un-certify, or delete a wrong
  mapping. A certified replay returns `source="certified"` and the chat shows a "✓ certified"
  trust marker. Verified end-to-end: ask → learned → certify → certified (for any phrasing
  variant that normalises to the same intent).

**All five gaps closed.** The build now matches the PPT reference architecture end to end:
question → intent (learned & certifiable) → semantic layer → spec → deterministic compiler
(with run-time-resolved periods) → SQL, plus a data-capture coverage safety net.
