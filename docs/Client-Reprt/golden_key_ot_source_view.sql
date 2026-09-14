-- =====================================================================
-- ⚠️ LEGACY / OPTIONAL as of 2026-08 — the rule engine now builds this join itself
-- from the spec's declarative `sources`/`joins` (see golden_key_ot_rule_spec.json),
-- so approach B needs NO deployed view. Kept only for reference / ad-hoc querying.
-- =====================================================================
-- Golden Key OT — thin JOIN source for the GENERIC RULE ENGINE (approach B)
-- Target DB: mint_goldenkey   |   Schema: custom_reports (client-scoped)
-- Apply as: mart owner / superuser.  Read by the rule engine as `source`.
--
-- WHY this existed:
--   The rule engine's `source` is a SINGLE table/view (one FROM). OT needs
--   attendance ⋈ leave, so we expose that join here as RAW daily columns —
--   NO classification, NO rollup. ALL the OT logic lives in the engine JSON
--   spec (golden_key_ot_rule_spec.json), not in this view.
--
--   Contrast with approach A (golden_key_ot_view.sql) which bakes the whole
--   classification+rollup into vw_ot_daily/vw_ot_monthly. Both were verified
--   to produce IDENTICAL per-employee OT (415 emps, 0 mismatch, 2026-07).
--
-- Dedupe: one leave row per (employee, day), priority Lieu > Full > Half > Short.
-- =====================================================================

CREATE SCHEMA IF NOT EXISTS custom_reports;

CREATE OR REPLACE VIEW custom_reports.vw_ot_source AS
SELECT
    a.employee_no, a.full_name, a.department, a.designation,
    a.year_no, a.month_no, a.year_month, a.work_date,
    a.is_public_holiday, a.worked_on_holiday, a.worked_hours,
    a.late_minutes, a.days_nopay,
    l.leave_category, l.day_portion, l.leave_minutes
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
) l ON true;

-- Reporting role reads the view (guarded — skip if the role is absent).
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'dw_readonly') THEN
    GRANT USAGE ON SCHEMA custom_reports TO dw_readonly;
    GRANT SELECT ON custom_reports.vw_ot_source TO dw_readonly;
  END IF;
END $$;
