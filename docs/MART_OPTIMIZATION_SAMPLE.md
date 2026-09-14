# Mart optimisation — VERIFIED against `enhance_marts` (fixes the DBT timeouts)

> Reviewed the actual models on branch `enhance_marts`. They are **well-built** —
> both already dedup/aggregate (`att_day` `DISTINCT ON`, payroll `salary_agg GROUP BY`),
> so this is **not** a naive join-explosion. The real, verified costs are below.
> `mart_daily_attendance` is **excluded** from the failing Phase-1 build and is already
> incremental; the Phase-1 timeout is in the base warehouse + the payroll mart's scope.

**Step 0 — profile first (don't guess which model is slow):**
```bash
dbt build --select <phase-1 scope> --no-partial-parse
jq '.results[] | {model:.unique_id, sec:.execution_time}' target/run_results.json | sort -k2 -n
```

---

## 1) `mart_processed_payroll_summary` — biggest win: `table` → `incremental`

**Why:** it is `materialized='table'` (full history rebuilt every run) and is in the
timed-out Phase-1 scope. Make it incremental so only new/changed periods rebuild.

```sql
-- config: table -> incremental
{{ config(
    materialized='incremental',
    unique_key=['tenant_id', 'employee_sk', 'payroll_period_sk'],
    incremental_strategy='delete+insert',
    on_schema_change='sync_all_columns',
    tags=['warehouse', 'warehouse_payroll', 'warehouse_marts'],
    indexes=[{'columns': ['tenant_id','employee_sk','payroll_period_sk'], 'unique': true}]
) }}

with salary as (
    select * from {{ ref('fct_processed_salary') }}
    {% if is_incremental() %}
      -- only rows changed since the last build, or any still-open period
      where process_timestamp >= (select coalesce(max(_refreshed_at), '1900-01-01')
                                    from {{ this }})
         or payroll_period_sk in (
              select payroll_period_sk from {{ ref('dim_payroll_period') }}
              where is_closed = false )
    {% endif %}
),
-- ... salary_agg (GROUP BY) and the rest stay exactly as they are ...
```
> Keep `salary_agg`'s `GROUP BY tenant_id, employee_sk, payroll_period_sk` and the
> `DISTINCT ON` — those are already correct. Only the `config` + the `salary` filter change.

---

## 2) `mart_daily_attendance` — three targeted fixes (no rewrite)

The model is structurally fine. Change only these three things.

### 2a. Remove `TRIM(x::text)=TRIM(y::text)` from the join predicates (biggest cost)
These sit **inside correlated LATERAL joins** → the cast+TRIM defeats the index →
a **sequential scan per row**. If `tenant_id` is the same type both sides, use direct
equality.

```sql
-- BEFORE (employee LATERAL):
WHERE TRIM(e.tenant_id::text) = TRIM(s.tenant_id::text)
      AND e.employee_sk = s.employee_sk
-- AFTER:
WHERE e.tenant_id = s.tenant_id
      AND e.employee_sk = s.employee_sk
```
Apply the same to the **shift_actual**, **shift_planned** and **approver** LATERALs
(`TRIM(sh.tenant_id::text)=TRIM(att.tenant_id::text)` → `sh.tenant_id = att.tenant_id`, etc.).
If tenant_id genuinely has whitespace/type drift, **normalise it once in staging**, not
in every join.

### 2b. Replace the correlated LATERAL dim lookups with `is_current` joins
Four correlated LATERALs run **once per output row**. If strict as-of-date SCD isn't
required for these dims (reporting usually wants the current name), a plain join is
1:1 and index-friendly:

```sql
-- BEFORE: LEFT JOIN LATERAL (SELECT ... FROM employee e WHERE ... ORDER BY as_of LIMIT 1) emp ON TRUE
-- AFTER:
LEFT JOIN employee emp
       ON emp.tenant_id = s.tenant_id
      AND emp.employee_sk = s.employee_sk
      AND emp.is_current = true

LEFT JOIN shift sh_actual
       ON sh_actual.tenant_id = att.tenant_id
      AND sh_actual.shift_sk  = att.shift_sk
      AND sh_actual.is_current = true

LEFT JOIN shift sh_planned
       ON sh_planned.tenant_id = s.tenant_id
      AND sh_planned.shift_sk  = coalesce(att.planned_shift_sk, sd.planned_shift_sk)
      AND sh_planned.is_current = true
```
> If as-of-date accuracy IS required, keep the LATERALs but still apply fix **2a**
> (removing the TRIM/cast) — that alone removes the per-row seq scan.
> The **approver** LATERAL can stay (it's a genuine top-1 pick) — just fix its TRIM.

### 2c. Dedup `fct_leave_daily` to one row per (employee, day)
Up to ~4 leave rows/day can multiply the spine. Pick one deterministically.

```sql
-- BEFORE:
leave_daily AS (
    SELECT ld.tenant_id, ld.employee_sk, ld.leave_date, ... , lt.leave_type_name, ls.status_code AS leave_status
    FROM {{ ref('fct_leave_daily') }} ld
    LEFT JOIN {{ ref('dim_leave_type') }} lt ON ...
    LEFT JOIN {{ ref('dim_leave_status') }} ls ON ...
    WHERE ld.leave_date >= ...
),
-- AFTER (add DISTINCT ON):
leave_daily AS (
    SELECT DISTINCT ON (ld.tenant_id, ld.employee_sk, ld.leave_date)
        ld.tenant_id, ld.employee_sk, ld.leave_date, ld.leave_application_sk,
        ld.leave_type_sk, ld.leave_status_sk, ld.leave_day_count, ld.is_half_day,
        ld.half_day_type, ld.superior_approved, ld.hr_approved,
        lt.leave_type_name, ls.status_code AS leave_status
    FROM {{ ref('fct_leave_daily') }} ld
    LEFT JOIN {{ ref('dim_leave_type') }} lt
        ON lt.leave_type_sk = ld.leave_type_sk AND lt.is_current = TRUE
    LEFT JOIN {{ ref('dim_leave_status') }} ls
        ON ls.leave_status_sk = ld.leave_status_sk
    WHERE ld.leave_date >= ...
    ORDER BY ld.tenant_id, ld.employee_sk, ld.leave_date, ld.leave_daily_sk
),
```
Everything else in the model (the `spine`, `att_day`, `joined` SELECT list, final SELECT)
stays exactly as is.

---

## 3) Build & timeout config

```bash
# first-time full load can be heavy ONCE — raise the timeout for that run only
DBT_RUN_TIMEOUT_SEC=21600        # 6h first load; incremental runs after are fast

# don't rebuild the whole warehouse for these two — target + upstream only
dbt build --select +mart_daily_attendance +mart_processed_payroll_summary
```

---

## Priority (do in this order)
```
0. Profile Phase-1 (run_results.json) → confirm the real slow models
1. Payroll: table → incremental               ← biggest, it's in the failing phase
2. Daily mart 2a: remove TRIM(::text) join predicates   ← removes per-row seq scan
3. Daily mart 2b/2c: is_current dim joins + leave dedup
4. Raise first-load timeout + targeted build
5. If base facts show up slow in the profile, make those incremental too
```

## One-liner for the tech lead
> Verified on `enhance_marts`: models already dedup/aggregate correctly — not a
> join-explosion. Real costs: (1) `mart_processed_payroll_summary` is a full-rebuild
> `table` in the timed-out phase → make it incremental; (2) `mart_daily_attendance` has
> `TRIM(x::text)=TRIM(y::text)` predicates inside correlated LATERAL joins → per-row
> seq scan → use direct equality and `is_current` joins, and dedup `fct_leave_daily`.
> Plus raise the first-load timeout and build targeted. No architecture change; marts
> stay physical/incremental.
