-- =====================================================================
-- Golden Key — Overtime Hours Monitoring Report  (FINAL view)
-- Target DB: mint_goldenkey   |   Schema: custom_reports (client-scoped)
-- Apply as: mart owner / superuser.  Read by the Report Builder.
--
-- Scope now: last completed months (May onward have full leave expansion).
-- Jan–Apr full-day leave is a known ELT gap (phase 2) — see the data-gaps brief.
--
-- Decisions baked in (2026-08, signed off):
--   • worked_hours is used AS-IS (no cap). The source records long/overnight/
--     multi-shift days as >24h and the client confirmed these are real, so the
--     qualifying-hours reflect them. `late_minutes` stays informational (§6:
--     worked_hours is already the net worked time; late is NOT deducted again).
--   • worked_on_holiday is now populated (holiday AND punched-in), so §11 uses it.
--
-- Source (daily grain):
--   mart.mart_attendance_daily (a)  — calendar, worked hours, holidays, no-pay
--   mart.mart_leave_daily      (l)  — leave classification (Short/Lieu/Full + portion)
--        LEFT JOIN LATERAL (deduped) on (employee_sk, date).
--
-- Confirmed value domains:
--   l.leave_category : 'Short Leave' | 'Lieu Leave' | 'Full Day Leave'
--   l.day_portion    : 'First Half'  | 'Second Half' | 'Full Day'
--
-- Golden Key policy constants: min_per_day=6, month_days=30, ph=8, halfday=4.
-- =====================================================================

CREATE SCHEMA IF NOT EXISTS custom_reports;

-- ---------------------------------------------------------------------
-- 1) Per employee × day: classify the day and compute qualifying hours.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW custom_reports.vw_ot_daily AS
WITH day AS (
    SELECT
        a.employee_sk, a.employee_no, a.full_name, a.department, a.designation,
        a.work_date, a.year_no, a.month_no, a.year_month,
        a.is_public_holiday, a.worked_on_holiday, a.worked_hours, a.late_minutes, a.days_nopay,
        l.leave_category, l.day_portion, l.leave_minutes,
        -- §6 adjusted worked hours = the source's net worked time, AS-IS (no cap).
        COALESCE(a.worked_hours, 0)::numeric AS adj_worked
    FROM mart.mart_attendance_daily a
    LEFT JOIN LATERAL (
        SELECT ld.leave_category, ld.day_portion, ld.leave_minutes
        FROM mart.mart_leave_daily ld
        WHERE ld.employee_sk = a.employee_sk
          AND ld.leave_date  = a.work_date
        ORDER BY CASE ld.leave_category
                   WHEN 'Lieu Leave' THEN 1 WHEN 'Full Day Leave' THEN 2
                   WHEN 'Short Leave' THEN 4 ELSE 3 END,
                 COALESCE(ld.leave_minutes, 0) DESC
        LIMIT 1
    ) l ON true
)
SELECT
    d.*,
    CASE
        WHEN d.is_public_holiday AND NOT d.worked_on_holiday      THEN 8                              -- §7  PH not worked
        WHEN d.worked_on_holiday                                  THEN d.adj_worked + 8               -- §11 PH worked
        WHEN d.leave_category = 'Lieu Leave'                      THEN 8                              -- §12 lieu day (transfer: phase 2)
        WHEN d.leave_category = 'Full Day Leave'
             OR d.day_portion = 'Full Day'                        THEN 8                              -- §9  full-day leave
        WHEN d.day_portion IN ('First Half', 'Second Half')       THEN d.adj_worked + 4               -- §8  half-day leave
        WHEN d.leave_category = 'Short Leave'                     THEN d.adj_worked
                                                                      + COALESCE(d.leave_minutes,0)/60.0 -- §10 short leave
        WHEN COALESCE(d.days_nopay, 0) > 0                        THEN 0                              -- §13 no-pay day
        ELSE d.adj_worked                                                                             -- §6  normal working day
    END AS day_qualifying_hours,
    CASE
        WHEN d.is_public_holiday AND NOT d.worked_on_holiday  THEN 'public_holiday'
        WHEN d.worked_on_holiday                              THEN 'public_holiday_worked'
        WHEN d.leave_category = 'Lieu Leave'                  THEN 'lieu'
        WHEN d.leave_category = 'Full Day Leave'
             OR d.day_portion = 'Full Day'                    THEN 'full_day_leave'
        WHEN d.day_portion IN ('First Half', 'Second Half')   THEN 'half_day_leave'
        WHEN d.leave_category = 'Short Leave'                 THEN 'short_leave'
        WHEN COALESCE(d.days_nopay, 0) > 0                    THEN 'nopay'
        ELSE 'normal'
    END AS day_category
FROM day d;

-- ---------------------------------------------------------------------
-- 2) Per employee × month: roll up, NPL-adjusted minimum, OT (§14/§15).
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW custom_reports.vw_ot_monthly AS
SELECT
    employee_sk, employee_no, full_name AS employee_name, department, designation,
    year_no, month_no, year_month,

    SUM(day_qualifying_hours) FILTER (WHERE day_category = 'normal')                 AS normal_hours,
    SUM(day_qualifying_hours) FILTER (WHERE day_category = 'public_holiday')         AS public_holiday_hours,
    SUM(day_qualifying_hours) FILTER (WHERE day_category = 'public_holiday_worked')  AS public_holiday_worked_hours,
    SUM(day_qualifying_hours) FILTER (WHERE day_category = 'half_day_leave')         AS half_day_leave_hours,
    SUM(day_qualifying_hours) FILTER (WHERE day_category = 'full_day_leave')         AS full_day_leave_hours,
    SUM(COALESCE(leave_minutes,0)/60.0) FILTER (WHERE day_category = 'short_leave')  AS short_leave_hours,
    SUM(day_qualifying_hours) FILTER (WHERE day_category = 'lieu')                   AS lieu_hours,
    SUM(COALESCE(days_nopay,0))                                                      AS npl_days,
    SUM(COALESCE(late_minutes,0))                                                    AS late_minutes,

    SUM(day_qualifying_hours)                                          AS total_qualifying_hours,
    30 * 6                                                             AS standard_minimum_hours,     -- 180
    (30 - SUM(COALESCE(days_nopay,0))) * 6                             AS applicable_minimum_hours,   -- (30 − NPL) × 6
    GREATEST(0, SUM(day_qualifying_hours)
                - (30 - SUM(COALESCE(days_nopay,0))) * 6)              AS ot_hours                    -- negative → 0
FROM custom_reports.vw_ot_daily
GROUP BY employee_sk, employee_no, full_name, department, designation,
         year_no, month_no, year_month;

-- Reporting role reads the views (guarded — skip if the role is absent).
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'dw_readonly') THEN
    GRANT USAGE ON SCHEMA custom_reports TO dw_readonly;
    GRANT SELECT ON custom_reports.vw_ot_daily, custom_reports.vw_ot_monthly TO dw_readonly;
  END IF;
END $$;

-- =====================================================================
-- KNOWN LIMITATIONS (documented; not blockers for the last-2-months report):
--   • §12 Lieu transfer — the source has no link from a lieu day back to the PH
--     it was earned from, so a PH-worked day and its lieu day both add 8h (rare:
--     ~34 lieu days). Needs a source-side link to net correctly. (Phase 2.)
--   • Jan–Apr full-day leave — not expanded into core.fct_leave_day for those
--     months (applications exist in fct_leave_request). ELT backfill. (Phase 2.)
--   • Verified live for 2026-07: 406 employees, OT computed per §14/§15.
-- =====================================================================
