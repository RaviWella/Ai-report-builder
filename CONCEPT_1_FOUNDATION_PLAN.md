# Concept 1 → Fully-SaaS: Foundation Workstream (Implementation Plan)

> Scope: Foundation 3 items (low effort, high trust). All changes **additive & backward-compatible** — new guards/endpoints default OFF or read-only. No existing behaviour breaks.

Grounded in actual code:
- Compiler: [compiler.py](backend/app/query_engine/compiler.py) — `compile_query()` → `CompiledQuery(statement, column_order)`
- Runner: [runner.py](backend/app/query_engine/runner.py) — `render_sql()` already renders parameterized SQL; `run_query()` is the only datamart-touching path
- Guards: [guards.py](backend/app/query_engine/guards.py) — `assert_select_only`, `resolve_row_limit`
- Connection: [datamart.py](backend/app/db/datamart.py) — per-tenant hardened read-only engine (already isolated pool per tenant)
- Service/API: [report_service.py](backend/app/services/report_service.py), [reports.py](backend/app/api/v1/reports.py)
- Tests: [test_query_engine.py](backend/tests/test_query_engine.py) — seed catalog via `build_seed_catalog()`

---

## Item 1 — SQL Preview + EXPLAIN endpoint (Gap 3: black-box SQL)

**Goal:** Builder/DBA ට ඕන spec එකකට *run කරන්නේ නැතුව* compiled SQL + query plan (cost/rows estimate) බලන්න පුළුවන්.

**New file `backend/app/query_engine/explain.py`**
- `Explain(stmt, analyze=False, fmt="json")` — SQLAlchemy `Executable/ClauseElement` with a `@compiles(..., "postgresql")` hook → `EXPLAIN (FORMAT JSON) <stmt>`. **`analyze=False` → query never executes** (just planner). Binds params correctly through SQLAlchemy (no string concat).
- `explain_plan(conn, compiled) -> {total_cost, est_rows, plan_json}` — runs EXPLAIN, parses top node's `Total Cost` / `Plan Rows`.

**`report_service.py`** — two methods:
- `explain_spec(ctx, data_spec, params) -> dict` — compiles unsaved spec (active catalog), renders SQL via `render_sql`, runs EXPLAIN on the hardened read-only connection. Returns `{sql, total_cost, est_rows, plan}`.
- `explain_template(ctx, template_id, params) -> dict` — same for a published template (pinned catalog).

**`reports.py`** — two endpoints (BuilderRoles):
- `POST /reports/preview-spec/explain` (body: `PreviewBody`)
- `POST /reports/{template_id}/explain` (body: `RunBody`)

**Safety:** EXPLAIN (no ANALYZE) is read-only & doesn't run the query; `default_transaction_read_only=on` already enforced. Inner statement still goes through normal compile guards. We do **not** feed the `EXPLAIN …` text through `assert_select_only` (the inner SELECT is what's validated).

**Tests:** `test_explain.py` — Explain construct compiles to `EXPLAIN (FORMAT JSON) SELECT …`, never `ANALYZE`; params stay bound (no inlined values).

---

## Item 2 — Golden SQL snapshot tests (Gap 2: compiler determinism)

**Goal:** හැම known spec → expected compiled SQL එක lock කරනවා. Compiler එක වෙනස් කරනකොට SQL වෙනස් වුණොත් test break වෙනවා → period-grain වගේ regressions catch වෙනවා; refactor safe වෙනවා.

**New `backend/tests/golden/`**
- `specs/*.json` — representative DataSpecs: `simple_select`, `grouped_agg_filter_sort`, `calculated_field`, `banding`, `metric`, `unpivot`, `two_period_marts`, `single_period_mart`.
- `expected/*.sql` — committed parameterized-SQL snapshots (via `render_sql`).
- `test_golden_sql.py` — parametrize over specs; `compile_query` → `render_sql` → compare to snapshot (whitespace-normalized). `UPDATE_GOLDEN=1` env rewrites snapshots (intentional updates only).

**Why deterministic:** bind-param names (`emp_status_1`, …) are deterministic for a given spec, so snapshots are stable across runs.

---

## Item 3 — Query cost governor (Gap 1: noisy-neighbour / runaway query guard)

**Goal:** 200 tenants — එක report එකක් mart එක saturate කරන්න දෙන්නේ නෑ. (Cross-tenant isolation **දැනටමත් partial**: `get_datamart_engine` per-tenant pool එකක් cache කරනවා, so එක tenant කෙනෙක්ගේ pool එක තව tenant ලාට බලපාන්නේ නෑ.)

**`config.py`** — new settings (default OFF):
- `query_cost_guard_enabled: bool = False`
- `query_max_estimated_cost: float = 0` (0 = no limit)

**`runner.py`** — inside `_execute()` (so **cache hits skip it**), before `conn.execute(statement)`:
- when guard enabled & threshold > 0: run `Explain(compiled.statement)` (Item 1 construct) on the same connection; if `total_cost > query_max_estimated_cost` → raise `guards.GuardError("This report is too large/expensive to run as-is — add a period filter or narrow it.")` → maps to HTTP 400.
- Only for full runs (preview already capped at 100 rows).

**Tests:** `test_cost_guard.py` — guard OFF (default) → no behaviour change; guard ON with low threshold → expensive spec raises GuardError (mock the EXPLAIN cost).

**Follow-up (noted, not in this item):** per-tenant pool-size tuning + concurrency caps for true QoS; documented in [CONCEPT_1_GAP_FIXES.md](CONCEPT_1_GAP_FIXES.md) Gap 1.

---

## Order of work
1. `explain.py` (shared by Item 1 + 3) + its test
2. Item 1 service methods + endpoints + test
3. Item 3 cost guard wiring + test
4. Item 2 golden snapshots + test
5. Run full `pytest`, confirm existing 53+ tests still pass.

## Done-when
- `POST /reports/preview-spec/explain` returns SQL + cost/rows for an unsaved spec.
- Golden suite green; editing the compiler to change SQL fails the suite until snapshots are updated.
- Cost guard OFF → identical behaviour; ON → rejects over-threshold queries with a clear message.
- No change to any existing endpoint's contract; all current tests pass.
