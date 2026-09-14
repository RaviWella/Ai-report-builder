# Concept 1 — Gap Fixes (SaaS-fit)

> Concept 1 (Mart + Job execute) එකේ දුර්වලතා 4ක් තිබුණා. මේ 4ම **එකම මූලික move එකකින්** විසඳෙනවා: dynamic compiler එක Concept 2 එක copy නොකර, **proper semantic engine** එකක් (Looker / Cube / dbt-MetricFlow / Malloy වර්ගයේ) බවට evolve කරන එක. Concept 1 එකේ self-service + dynamic ස්වභාවය නැති නොකර gaps වහනවා.

## මූලික අදහස (single unifying move)

> **Compiler එක තනි entry point එකක් විදිහට තියාගෙන, ඒකට (a) richer *declarative* model එකක්, (b) *materialization / aggregate-awareness* tier එකක්, (c) SQL transparency, සහ (d) AI optional drafting layer එකක් දෙන එක.**

මේකෙන් gap 4ම වැහෙනවා — එකින් එක පහළ.

---

## Gap 1 — Performance unpredictable (no hand-tuned joins)

### මූල හේතුව
හැම query එකක්ම base mart tables මතින් live generate වෙනවා. Heavy/repeated reports වලට pre-built, tuned source එකක් නෑ.

### Solution — **Aggregate Awareness + Materialization Promotion** (Looker PDT / Cube pre-aggregation pattern)

දෙ-tier model එකක්:

1. **Long tail (95% reports)** → දැනට වගේම dynamic compile, base tables, + Redis result cache. මේවාට tuning ඕනේ නෑ.
2. **Hot set (heavy/frequent reports)** → compiler එක *cheapest available source* එක තෝරනවා:
   - Catalog එකේ entity එකකට **rollup / aggregate sources** declare කරන්න පුළුවන් (e.g. `payroll_monthly_by_dept` — pre-aggregated materialized view).
   - Compiler එක spec එක බලලා: "මේ query එක answer කරන්න rollup එකක් තියෙනවද?" → තිබුණොත් base table එක වෙනුවට rollup එක hit කරනවා. **Spec එක වෙනස් වෙන්නේ නෑ; source resolution විතරයි වෙනස්.**

**Promotion path (automation):**
- Run log එකේ දැනටමත් `compiled_sql_hash + duration_ms + row_count` තියෙනවා. Slow/frequent sql_hash patterns surface කරලා → ඒ shape එකට aggregate/materialized view එකක් (dbt model එකක්) auto-suggest හෝ generate කරන්න. මෙතනදී තමයි Concept 2 එකේ dbt එක **borrow** කරන්නේ — නමුත් long tail එකට නෙවෙයි, hot set එකට විතරයි.

**Multi-tenant win:** 200 tenants ලාගේ schema එක සමාන නිසා, rollup definition එක **share** කරලා per-tenant materialize කරන්න පුළුවන් (dbt `{{ ref() }}` per-tenant resolve — Concept 2 පැත්තෙන්ම).

**Add a query governor (noisy-neighbour guard):** run කරන්න කලින් `EXPLAIN` cost estimate එකක් → threshold එක ඉක්මෙව්වොත් queue/reject/downsample. 200 tenants වලට එක tenant කෙනෙක්ට mart එක saturate කරන්න දෙන්නේ නෑ.

**Touch:** `compiler.py` (source resolution), `semantic.py` (entity එකට `aggregates[]`), `runner.py` (cost guard), new `aggregate_advisor` (run-log analysis).

---

## Gap 2 — Compiler complexity (edge cases in code, e.g. period-grain)

### මූල හේතුව
Period-grain join, fan-out වගේ logic backend code එකේ hardcode වෙලා. හැම අලුත් edge case එකක්ම compiler එක patch කරනවා.

### Solution — **Declarative grain/join model + Symmetric Aggregates + Golden tests**

1. **Joins & grain = data, not code.** `period-grain-join-fix` (memory) එකේ root cause එක = fan-out join එකකදී measures duplicate වෙන එක. මේක code එකේ special-case කරනවා වෙනුවට:
   - Entity එකේ **grain** (`primary_key` + `period_grain` දැනටමත් තියෙනවා) full ව declare කරන්න.
   - Join එකක් fan-out එකක්ද කියලා catalog එකෙන්ම infer කරන්න (one-to-many → measures duplicate වෙයි).
   - **Symmetric aggregates** apply කරන්න (Looker/Malloy pattern): fan-out join එකකදී measure එකක් `SUM` කරනකොට, duplicate rows neutralize කරන්න primary-key-aware aggregation එකක් generate කරනවා. මේක එක general algorithm එකක් — හැම period-grain report එකකටම වැඩ කරනවා, special-case නෑ.

2. **Golden SQL snapshot tests.** හැම known spec → expected compiled SQL එක test fixture එකක්. Edge case එකක් fix කරනකොට test එකක් එනවා → regression block වෙනවා. Compiler determinism එක locked.

**Touch:** `sql_builder.py` (symmetric agg in aggregation build), `guards.py` (fan-out detection), `semantic.py` (join cardinality metadata), new `tests/golden/` snapshot suite.

---

## Gap 3 — Black-box SQL (DBA predict කරන්න බෑ)

### Solution — **SQL Transparency + DBA approval lane + observability**

1. **`/compile/preview` endpoint** — ඕන spec එකකට run කරන්නේ නැතුව compiled SQL + `EXPLAIN` plan එක return කරනවා. Builder UI එකේ "View SQL" button එකක්.
2. **Published version එකේ SQL text එක store කරන්න** — දැනට `sql_hash` විතරයි; actual SQL text එකත් save කරන්න. ඒ වෙලාවට DBA review/approve lane එකක් දාන්න පුළුවන් (certified reports වලට — Concept 2 governance එක මෙතන එනවා).
3. **SQL shape observability** — distinct `compiled_sql_hash` patterns + frequency + p95 latency dashboard එකක්. DBA ට මේකෙන් **index/materialize කරන්න ඕනේ මොනවද** කියලා data-driven ව තීරණය කරන්න පුළුවන් (Gap 1 promotion path එකම feed කරනවා).

**Touch:** new `api/compile_preview`, `report_service.py` (store sql_text), audit/observability table.

---

## Gap 4 — AI dependency (NL→spec quality)

### මූල හේතුව
NL→spec path එක AI/glossary/metrics config මත රඳා පවතිනවා කියන perception එක.

### Solution — **AI = optional drafting layer; deterministic DataSpec = contract**

මෙතන key insight එක: **DataSpec එක තමයි contract එක, AI නෙවෙයි.** AI වැරදුණත් system එක break වෙන්නේ නෑ — spec එක validate වෙනවා.

1. **Builder එක AI නැතුවත් සම්පූර්ණයෙන් usable කරන්න** — catalog එක මතින් point-and-click. AI = accelerator, *required path එකක් නෙවෙයි.* (200 tenants වලින් සමහරු AI off කරන්න කැමති වෙයි — data residency.)
2. **Deterministic-first resolution** — glossary/metric exact + fuzzy match මුලින්ම (memory: local-fuzzy-first), AI **leftovers වලට විතරයි**. දැනටමත් මේ දිශාවට — strengthen කරන්න.
3. **Validation + clarification loop** — AI spec එක guards වලින් validate (refs valid, joins reachable). Fail වුණොත් → silent fail නැතුව user ට clarify කරන්න අහනවා.
4. **NL→spec eval harness** — golden question→spec set එකක් (per tenant නම් වඩා හොඳයි). Model version pin කරන්න; regression catch කරන්න. Determinism = measurable, perception එකක් නෙවෙයි.

**Touch:** Builder UI (full manual mode), resolver (deterministic-first ordering), new `tests/nl_eval/` harness, guards (clarify-on-fail).

---

## SaaS-fit rollout (prioritized)

| # | Fix | Impact | Effort | Priority |
|---|-----|--------|--------|----------|
| 1 | **SQL preview + EXPLAIN endpoint** (Gap 3) | DBA trust, debugging, feeds everything | Low | 🟢 කරන්න මුලින්ම |
| 2 | **Golden SQL snapshot tests** (Gap 2) | Compiler determinism lock, safe refactor | Low | 🟢 මුලින්ම |
| 3 | **Query governor / cost guard** (Gap 1) | Noisy-neighbour protection — 200 tenants critical | Med | 🟡 |
| 4 | **Symmetric aggregates + declarative grain** (Gap 2) | period-grain bug root fix, no more special-cases | Med | 🟡 |
| 5 | **Aggregate awareness + materialization promotion** (Gap 1) | heavy-report perf, the big one | High | 🟠 |
| 6 | **Deterministic-first resolver + eval harness** (Gap 4) | AI reliability, optional AI | Med | 🟡 |
| 7 | **DBA approval lane + certified reports** (Gap 3) | governance (borrow Concept 2) | Med | 🟠 |

### සරලව
- Gap 4ම **Concept 1 එක semantic engine එකක් බවට පත් කිරීමෙන්** විසඳෙනවා — Concept 2 එක copy කිරීමෙන් නෙවෙයි.
- Concept 2 එකෙන් **target ව borrow කරන්නේ දෙකයි:** (1) heavy/hot reports වලට dbt materialized views (long tail එකට නෙවෙයි), (2) certified reports වලට governance/approval lane.
- මුලින්ම **transparency (preview) + golden tests + cost guard** කරන්න — low effort, high trust, ඉතුරු වැඩ වලට foundation එක.
- Big-ticket item එක = **aggregate awareness** (Gap 1). ඒක තමයි "performance unpredictable" එක permanently වහන්නේ, dynamic ස්වභාවය නැති නොකර.
