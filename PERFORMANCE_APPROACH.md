# Dynamic Performance — Strong Technical Approach

> ගැටලුව: fully-dynamic compiler එකක (Concept 1) හැම query එකක්ම base mart tables මතින් live generate වෙනවා — tuned views නෑ. Heavy/repeated reports → slow, mart එකට බර. **Manual views දාන්න බෑ** (ඒක Concept 2 ට වැටීම; dynamic vision එක නැති වෙනවා). ඒ නිසා slowness එක **dynamic-friendly layers** වලින් solve කරනවා.

මූලික strategy එක Looker/Cube/Druid වල proven pattern එකම: **query routing engine** — spec එකකට, *cheapest source that can answer it* තෝරනවා. Spec එක නොවෙනස්; source resolution විතරයි smart වෙනවා.

---

## Layered approach (cheapest → deepest)

### Layer 0 — Measure first (blind optimize කරන්න එපා) 🟢
දැනටමත් `ReportRun` එකේ `duration_ms`, `compiled_sql_hash`, `row_count`, `snapshot_ref` තියෙනවා.
- **Slow-query view:** `sql_hash` එකෙන් group කරලා → p50/p95 latency, frequency, avg rows. → "hot + slow set" එක (top 20 query shapes) identify වෙනවා.
- EXPLAIN endpoint (foundation Item 1) එකෙන් plan/cost එක.
- **මේකෙන් තමයි ඉතුරු හැම layer එකකම targets එනවා** (මොන rollups, මොන indexes). Optimize කරන්නේ data එකෙන්, අනුමානෙන් නෙවෙයි.

### Layer 1 — Required period filter + filter push-down 🟢 (huge, cheap)
- Period-grained marts (payroll/paysheet/attendance) — **period filter නැතුව full history scan** වෙනවා. (Memory: "Part 2 required period filter pending".)
- **Fix:** period-grained entity එකක් යොදන report එකකට period filter එකක් **mandatory** කරන්න (default = latest period). → scan size එක 10×–100× අඩු වෙනවා එකම change එකෙන්.
- Filters compile-time push-down (දැනටමත් parameterized WHERE — confirm pushed to base, not post-join).

### Layer 2 — Result + compiled-SQL caching 🟢 (repeated queries free)
- Result cache (snapshot-keyed) දැනටමත් තියෙනවා — strengthen:
  - **Compiled-SQL cache** (recompile මඟ හරිනවා — spec → SQL deterministic).
  - **Proactive warming:** snapshot change වුණාම, popular/scheduled reports background එකේ pre-compute → user මුල් hit එකේම cache hit.
- මේක repeated-query slowness solve කරනවා; first-run slowness නෑ → Layer 3.

### Layer 3 — Aggregate awareness / pre-aggregation ⭐ (THE big one)
මේක තමයි dynamic-perf එක permanently වහන core එක.

**අදහස:** coarser-grain **rollup tables** set එකක් materialize කරනවා (e.g. `headcount by dept by month`, `payroll totals by dept by period`). Compiler එක spec එකක් එනකොට:

```
choose_source(spec, catalog):
  candidates = [base_table] + entity.aggregates   # rollups declared in semantic layer
  for agg in aggregates (coarsest first):
     if spec.group_by ⊆ agg.dimensions
        and spec.measures ⊆ agg.measures
        and spec.filters only use agg.dimensions:
         return agg            # route to rollup  (10K rows, not 10M)
  return base_table            # long tail falls back to base (correct, just slower)
```

- **Transparent:** spec එක නොවෙනස්; FROM clause එක විතරයි rollup එකට resolve වෙනවා.
- **Coverage:** rollups Layer-0 hot-set එක cover කරනවා; long tail base එකට. (Fully-dynamic තවම — හැම combo එකක්ම answerable.)
- **Correctness:** additive measures (sum/count) විතරයි rollup-safe; avg → sum/count වලින් re-derive; count-distinct rollup-unsafe (base එකට route). Compiler මේක check කරනවා.
- **Freshness:** rollups `snapshot_ref` එකට keyed; snapshot change → rollup refresh (dbt model එකක් හෝ refresh task). පරණ snapshot එකේ rollup එක stale උනොත් route කරන්නේ නෑ.

**Semantic layer addition:** `Entity.aggregates: [AggregateSource]` —
```
AggregateSource(physical_table, schema, dimensions:[ref], measures:[ref],
                grain, snapshot_keyed=True)
```
→ ඔයාගේ semantic-layer enhancement එකට කෙලින්ම සම්බන්ධ (deep-dive §6 #8).

### Layer 4 — Warehouse physical tuning (data-driven) 🟡
Layer-0 + EXPLAIN වලින් targets:
- Indexes — common filter/join/group columns (`employee_sk`, `payroll_year/month`, `department`).
- Period marts → **partition by (year, month)**.
- Report builder මේවා **recommend** කරනවා (slow-query analysis එකෙන්); DBA apply කරනවා. (Dynamic vision බිඳෙන්නේ නෑ — මේවා physical tuning, report-specific views නෙවෙයි.)

### Layer 5 — Compiler correctness/efficiency 🟡
- **Symmetric aggregates** — fan-out joins (period-grain) row explosion fix → less data, correct numbers. (Drill-down + cardinality work එකට ties වෙනවා.)
- Only-needed-columns (දැනටමත් `collect_columns`) — confirm; no SELECT *.

### Layer 6 — Cost governor + async heavy work 🟡
- **EXPLAIN cost guard** (foundation Item 3) — runaway query reject/queue → p95 protect, noisy-neighbour.
- **Async exports** — heavy exports Celery එකට → interactive reports fast තියෙනවා.

---

## ප්‍රමුඛතා පිළිවෙළ (recommended build order)

| # | Layer | Impact | Effort | |
|---|---|---|---|---|
| 1 | Slow-query observability (L0) | targets for everything | Low | 🟢 මුලින්ම |
| 2 | Required period filter (L1) | huge scan reduction, cheap | Low | 🟢 |
| 3 | Cost governor (L6) | noisy-neighbour protect | Low-Med | 🟢 |
| 4 | Caching strengthen + warming (L2) | repeated queries free | Med | 🟡 |
| 5 | **Aggregate awareness (L3)** | **the permanent fix** | High | 🟠 core |
| 6 | Index/partition recommendations (L4) | base-query speedup | Med (+DBA) | 🟡 |
| 7 | Symmetric aggregates (L5) | correctness + less data | Med | 🟡 |

**Quick wins (week 1):** L0 + L1 + L6 — low effort, immediate p95 improvement, සහ aggregate-awareness එකට data/targets හදනවා.
**Core (the real fix):** L3 aggregate awareness — මේක තමයි "dynamic but fast" කරන්නේ.

---

## මූලික insight
> Manual views = Concept 2 (fast, not dynamic). Aggregate awareness = **same speed benefit, fully dynamic**. Rollups report-specific නෑ — ඒවා **reusable coarse cubes**; compiler ඕන report එකකට ඒවා auto-route කරනවා. ඒකයි fully-dynamic SaaS එකකට හරි answer එක.

## Touch points
| Layer | File |
|---|---|
| L0 observability | `ReportRun` queries + new admin endpoint |
| L1 required period | [compiler.py](backend/app/query_engine/compiler.py), [report_service.py](backend/app/services/report_service.py) |
| L2 caching | [services/result_cache.py](backend/app/services/result_cache.py), [runner.py](backend/app/query_engine/runner.py) |
| L3 aggregate awareness | [domain/semantic.py](backend/app/domain/semantic.py) (`AggregateSource`), [compiler.py](backend/app/query_engine/compiler.py) (`choose_source`), refresh job |
| L4 tuning | warehouse + recommendation report |
| L5 symmetric agg | [sql_builder.py](backend/app/query_engine/sql_builder.py), [compiler.py](backend/app/query_engine/compiler.py) |
| L6 governor | [runner.py](backend/app/query_engine/runner.py), [query_engine/explain.py](backend/app/query_engine/explain.py) (new) |
