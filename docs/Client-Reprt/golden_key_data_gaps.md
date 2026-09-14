# Golden Key — Overtime Report: Data Findings & Deploy Brief

Prepared from a live review of `mint_goldenkey` (via read-only). For the DW/DevOps
and source teams. The **last-2-months (Jun–Jul 2026) OT report is ready to ship** —
none of the open gaps block it.

---

## 1. Deploy the report views

Apply **`golden_key_ot_view.sql`** to `mint_goldenkey` as the mart owner / superuser.
It creates `custom_reports.vw_ot_daily` and `custom_reports.vw_ot_monthly` (client-
scoped schema — NOT the shared `mart` schema) and grants SELECT to `dw_readonly`.

Verified live for 2026-07: **406 employees, OT computed per the FRS (§14/§15).**

---

## 2. Decisions already made (no action needed)

- **worked_hours used AS-IS (no cap).** The source records long/overnight/multi-shift
  days as **>24h** (max 40.2h; ~130–256 rows/month). The client confirmed these are
  real, so qualifying hours reflect them. *This is a source value, not a mart bug.*
  (Optional: source team may still document WHY a day can exceed 24h.)

---

## 3. Data gaps — fix for full history (NOT blocking the last-2-months report)

| # | Gap | Layer | Detail | Report impact |
|---|-----|-------|--------|---------------|
| 1 | **Full-day leave missing Jan–Apr 2026** | ELT — `core.fct_leave_day` | Annual/Casual/Sick/Nopay leaves are **not expanded into daily rows** for Jan–Apr (only Short+Lieu are). Applications DO exist (`fct_leave_request` / `mart_leave_request`). Full expansion starts **May**. | Jan–Apr OT would miss full-day-leave days (8h each). **Phase 2.** |
| 2 | **shift_start_time / shift_end_time = 0% in mart** | mart-mapping | The data exists in `core.dim_shift` (start/end times, 119 shifts) but doesn't flow to `mart_attendance_daily`. | Not needed for the current OT logic (worked_hours is net), but wire it for completeness. |
| 3 | **§12 Lieu → PH-date link missing** | source | `hr_lieu_leave` records `lieu_lv_date` (when taken) but has **no reference to the public-holiday date it was earned from**. So the "move 8h from the PH date to the lieu date" cannot be netted. Rare (~34 lieu days). | PH-worked +8 AND lieu day +8 both count (possible double-count). **Phase 2 / source enhancement.** |

---

## 4. Sanity check to confirm (quick)

- **Many employees show as "Absent" all month** (day_status: Week Off 43%, Absent 37%,
  Present 10%). For 2026-07 the **median employee OT is 0** — only a subset are active.
  Please confirm this is expected (inactive/seasonal roster) and NOT a `worked_hours`
  coverage gap for part of the workforce.

---

## 5. Summary

- ✅ **Ship now:** deploy the views → Jun–Jul OT report is live and correct (leave
  fully expanded May+; worked_hours accepted as-is per the client).
- ⏳ **Phase 2 (full history):** ELT fix for Jan–Apr full-day-leave daily expansion (#1),
  shift-time mart mapping (#2), and the lieu→PH source link (#3).
- ❓ Confirm the "Absent majority" (§4) is real.
