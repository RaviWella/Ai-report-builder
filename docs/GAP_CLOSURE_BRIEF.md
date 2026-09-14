# Development Brief — Bring mint-analytics' rigor into Mint-Report-Builder

> **How to use this file:** This is a prompt/brief for a coding agent. Hand it the whole
> file (or one workstream at a time). It describes WHAT to build and the acceptance
> criteria — it does not prescribe exact code. Keep all existing behavior working;
> everything here is additive hardening.

---

## Context (read first)

**This project (`Mint-Report-Builder`)** already has a strong, modern semantic layer:
a per-tenant metadata catalog (`app/domain/semantic.py`), a runtime query compiler
(`app/query_engine/compiler.py`), read-only guards (`app/query_engine/guards.py`),
version pinning (`semantic_version_ref`), and an AI boundary where the model sees only
`metadata_for_ai()` and returns a validated `DataSpec` (`app/services/ai_service.py`).

**The sister project (`mint-analytics`)** is a finance-intelligence platform with several
*rigor* properties this project does not yet have. The tech lead's instruction is:
**keep this project's architecture as the base, and develop into it the strong things
that mint-analytics has and this project lacks.** Do **not** rework mint-analytics.

**Primary goals, in priority order:**
1. **Data accuracy** — prove every report number is correct and traceable.
2. **Reduce LLM dependency** — common reports must resolve with zero LLM calls; LLM becomes
   a fallback for genuinely ambiguous requests only, and never runs at report *run* time.
3. **Accuracy continuity** — a published report reproduces the *same* numbers over time,
   even as the datamart and catalog evolve.

**Hard constraints (do not violate):**
- Keep multi-tenancy and zero-touch bootstrap intact.
- The AI must still never see physical names, data, or PII.
- The query path stays read-only and parameterized (no string-concatenated SQL).
- Existing reports and their pinned `semantic_version_ref` must keep working unchanged.

---

## Workstream 1 — Data accuracy: run lineage + checksums (mint-analytics' `rules_sha` idea)

**Why:** mint-analytics stamps every mart row with `rules_sha` and logs every run, so any
number can be traced to the exact rules + run that produced it. This project pins the
*semantic version* but does not record *what was actually produced* on each run.

**Build:**
1. A **report-run log** (new table, per tenant) capturing, for every executed report:
   `run_id`, `tenant_id`, `report_id`, `semantic_version_ref`, `compiled_sql_hash`
   (SHA-256 of the final compiled SQL text), `row_count`, `result_checksum`
   (deterministic hash of the ordered result set), `datamart_snapshot_ref` (see WS-3),
   `executed_at`, `executed_by`, `duration_ms`, `status`.
2. Compute `compiled_sql_hash` in the compiler/runner and `result_checksum` in the runner.
3. Surface these on the export footer / report metadata so a viewer can see
   "version vX, run <id>, checksum <…>" — audit-grade provenance.

**Acceptance criteria:**
- Re-running the same report against the same datamart snapshot yields an **identical**
  `result_checksum`. A change in data, catalog version, or spec changes the checksum.
- Every export carries its `run_id` + `semantic_version_ref` + `result_checksum`.

---

## Workstream 2 — Reduce LLM dependency: deterministic NL → spec path

**Why:** mint-analytics' core uses a deterministic intent engine (keyword + regex), no
runtime LLM. This project calls a real LLM to turn natural language into a `DataSpec`.
The fuzzy-match-first pattern already exists for Excel mapping (`_map_columns`) — extend
that philosophy to natural-language report requests.

**Build:**
1. A **deterministic intent/spec resolver** that handles the common report shapes without
   any LLM call: pattern-match the request against the catalog's labels/refs/entities to
   produce a `DataSpec` directly (fields + group_by + simple filters + aggregations).
   Reuse the existing normalize + fuzzy-match helpers (`_norm`, `_local_match`).
2. **Tiered resolution:** (a) deterministic resolver first → if it produces a confident,
   guard-valid spec, return it with `source="deterministic"`; (b) only fall back to the
   LLM for requests the deterministic path cannot confidently resolve, tagged
   `source="llm"`; (c) the existing `_validate` (Pydantic + guards) runs on **both** paths.
3. Record `source` (deterministic vs llm) in the audit log so LLM-usage rate is measurable.

**Acceptance criteria:**
- A defined set of "common request" test cases resolves with **zero** LLM calls.
- LLM is invoked only for the ambiguous remainder, and never at report run time.
- Every spec — deterministic or LLM — still passes `validate_refs` + `validate_joins`.
- A metric/log shows the share of requests served deterministically (target: most).

---

## Workstream 3 — Accuracy continuity: datamart snapshot pinning + validation gates

**Why:** mint-analytics has period locking, watermarks, and dbt assertion tests, so a
published period's numbers don't silently change and bad data can't be served. This
project pins the *mapping* version but not the *data* state, and runs no pre-serve checks.

**Build:**
1. **Datamart freshness / snapshot reference:** capture a `datamart_snapshot_ref` per
   tenant (e.g. a max-`_refreshed_at` / load-watermark read from the datamart) and record
   it on every report run (WS-1). This lets "reproduce this exact report" mean *same
   catalog version + same data snapshot*.
2. **Validation gates (assertion checks):** a small, declarative set of data-quality
   assertions runnable against a tenant's datamart (e.g. non-negative measures where
   expected, period/grain uniqueness on summary marts, referential coverage of join keys).
   Store results (pass/fail + details). Mirror mint-analytics'
   `mart_validation_result` concept.
3. **Serve policy:** surface validation status with a report; optionally block / warn when
   a critical assertion is failing for the data a report depends on.

**Acceptance criteria:**
- Each report run records the `datamart_snapshot_ref` it ran against.
- Assertions can be run on demand and their results stored and queryable.
- A failing critical assertion is visible to the builder/viewer (warn or block, per config).

---

## Workstream 4 — Defense-in-depth security: DB-level read-only role (mint-analytics' `ai_reader`)

**Why:** mint-analytics blocks raw access at the **database** with a role
(`ai_reader` granted only the semantic views). This project enforces read-only in the
**app** (read-only user + read-only txn + `assert_select_only`). One app-layer bug could
leak data; a DB role would still block it. Add the DB layer *in addition to* the app guards.

**Build:**
1. A **DB-level read-only role** per the datamart, with `SELECT`-only grants scoped to the
   tenant's allowed semantic schema(s) (`hr_semantic` / the views), and **no** access to
   raw/staging tables. The runtime connection uses this role.
2. Confirm `search_path` / schema scoping is enforced at connection level alongside the role.
3. Keep all existing app-layer guards — this is belt **and** braces, not a replacement.

**Acceptance criteria:**
- With the app guards hypothetically disabled, the DB role alone still rejects any
  write/DDL and any read of raw/non-semantic tables.
- Existing report execution continues to work through the new role.

---

## Workstream 5 — Deterministic evaluation: remove `eval()` from calculated fields

**Why:** `compiler.py::_parse_calc` uses `eval(safe_expr, {"__builtins__": {}}, namespace)`
(`# noqa: S307`). It's tokenizer-guarded, but it is still `eval`. mint-analytics' rigor goal
is full determinism with no dynamic execution.

**Build:**
1. Replace the `eval` with an **AST-based evaluator**: `ast.parse(expr, mode="eval")`, walk
   the tree, and allow only a whitelist of nodes (numbers, names→bound columns, parentheses,
   and the four arithmetic binary ops + unary minus). Reject anything else with a `GuardError`.
2. Keep the existing public behavior of `_parse_calc` and its tests green.

**Acceptance criteria:**
- No `eval`/`exec` anywhere in the query engine.
- All existing calculated-field and banding tests pass unchanged; malformed expressions
  still raise `GuardError`.

---

## Suggested order & sequencing

1. **WS-5** (small, self-contained, immediate safety win).
2. **WS-4** (DB role — infra change, unblocks the security story).
3. **WS-1** (run lineage + checksums — foundation the others report into).
4. **WS-3** (snapshot pinning + validation — builds on WS-1).
5. **WS-2** (deterministic NL path — largest, do last; it benefits from the run-log metrics).

Each workstream should ship with tests and leave existing tests green. Do not start a
workstream by refactoring unrelated code — keep diffs scoped to the goal.

---

## Out of scope (do NOT do)

- Rebuilding the catalog/compiler architecture — it stays as the base.
- Removing the LLM entirely — it stays as a build-time fallback (WS-2 only *reduces* reliance).
- Any change to mint-analytics.
- Frontend redesign — only surface the new provenance/validation metadata where reports
  are previewed/exported.
</content>
