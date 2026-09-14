# Golden Key OT — Approach A vs Approach B, cross-verified

Two independent builds of the SAME report, proven to produce identical numbers.

| | Approach A — mart view | Approach B — generic rule engine |
|---|---|---|
| Logic lives in | hand-written SQL (`golden_key_ot_view.sql`) | declarative JSON (`golden_key_ot_rule_spec.json`) |
| Source | attendance ⋈ leave inside the view | **the engine builds the join itself** from the spec's `sources`/`joins` — reads `mart.mart_attendance_daily` ⋈ `mart.mart_leave_daily` directly |
| Hand-written SQL per client | one view per client | **ZERO** — 100% JSON |
| Per client | new SQL each time | **same engine, new JSON** ← long-term |
| Governance | SQL reviewed per client | no raw SQL / no eval; JSON → whitelisted AST → parameterized SQL |

> **Declarative joins (2026-08).** B originally needed a thin hand-written join view
> (`custom_reports.vw_ot_source`) because the engine read a single table. The engine now
> expresses multi-table joins in the spec itself (`sources` + per-source `join`, incl. a
> `left_pick_one` LATERAL that keeps one row per base row by `priority`). **B needs no
> deployed custom view at all** — a new rule-heavy client report is now pure JSON.

## Result (live, `mint_goldenkey`, 2026-07)

Full report, including the per-category breakdown — **all 12 columns identical for
every one of 415 employees:**

```
total_emps   = 415      missing_side = 0
normal_hours ................ OK    lieu_hours ............ OK
public_holiday_hours ........ OK    npl_days .............. OK
public_holiday_worked_hours . OK    late_minutes .......... OK
half_day_leave_hours ........ OK    total_qualifying ...... OK
full_day_leave_hours ........ OK    applicable_min ........ OK
short_leave_hours ........... OK    ot_hours .............. OK
TOTAL column mismatches across all employees: 0   →  ✅ A == B
```

Top earners cross-check exactly (e.g. emp 3548 → 190.82 = 190.82; emp 3565 →
183.35 = 183.35).

**Conclusion:** the generic engine (B) is correct against the reference view (A). B is
the long-term path — every future rule-heavy client report is authored as JSON, not
hand-written SQL.

## Bugs the A==B build caught (the view is the oracle)

1. **Phantom function-name column.** `_source_columns` treated **function names**
   (`coalesce`, `greatest`, …) as physical source columns → phantom
   `vw_ot_source.coalesce`. Any spec whose `define`/`value` used a function would fail
   at runtime. Fixed (exclude `_FUNCTIONS`) + `test_function_names_are_not_source_columns`.
2. **Output name shadowing a source column.** Adding the breakdown revealed that a
   rollup like `sum(late_minutes) AS late_minutes` (output name == source column it
   reads) dropped the source column, because rollup/compute **output** names were
   subtracted from the per-row **source** columns. They live in different scopes; fixed
   by reserving only per-row names + `test_rollup_output_may_share_a_source_column_name`.
3. **NULL tiebreak silently winning the row-pick.** When the engine started building the
   `left_pick_one` join itself, it emitted `leave_minutes DESC` — but Postgres defaults
   DESC to **NULLS FIRST**, so a leave row with a NULL `leave_minutes` won the pick. A
   day can carry both `Short Leave / Hours (30 min)` and `Short Leave / Full Day
   (NULL min)`; `day_portion='Full Day'` classifies as **full-day leave (8h)** while
   `'Hours'` is **short leave**. Picking the NULL row flipped the day — **44 employees'
   OT was wrong** in the first multi-source run. Fixed: tiebreak is `NULLS LAST` both
   directions (a missing tiebreak value must never win) + `test_multi_source_...`. This
   is the highest-value catch of the whole A==B exercise.

## Engine features added

- **`row_cases`** — extra labeled per-row derivations (e.g. a `day_category` tag)
  evaluated alongside `day_value`, usable in rollup FILTER breakdowns
  (`sum(day_value) where day_category == 'normal'`). Enables the full per-category
  monthly breakdown in JSON.
- **Declarative multi-source joins** — `sources` (first = base/driving table) + per
  source `join`: `left` / `inner` / `left_pick_one` (LATERAL, keeps one row per base row
  by `priority` = ordered category ranks + a NULLS-LAST tiebreak). Column names are
  unique across sources so expressions stay unqualified; a shared join key may appear in
  both sources (it's structural) but referencing an ambiguous column is a compile error.

Both are general engine primitives, not OT-specific.

## To run B in production

1. **No custom view to deploy** — the engine reads `mart.mart_attendance_daily` and
   `mart.mart_leave_daily` directly and builds the join. (`golden_key_ot_source_view.sql`
   is now optional/legacy.)
2. Create the rule report from the JSON: **Rule Report** page (paste
   `golden_key_ot_rule_spec.json`) → or `POST /templates/rule-report`.
3. Run for any month via the `date_from` / `date_to` filters.
