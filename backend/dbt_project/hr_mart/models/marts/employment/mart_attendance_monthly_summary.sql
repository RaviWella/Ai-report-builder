-- =============================================================================
-- mart_attendance_monthly_summary
-- Pre-aggregated per employee × month for attendance + OT. Incremental window
-- on recent months to absorb late-arriving attendance edits.
-- =============================================================================

{{ config(
    materialized='incremental',
    unique_key=['tenant_id', 'employee_sk', 'year', 'month_number'],
    incremental_strategy='delete+insert',
    on_schema_change='sync_all_columns',
    tags=['warehouse', 'warehouse_marts']
) }}

WITH attendance AS (
    SELECT * FROM {{ ref('fct_daily_attendance') }}

    {% if is_incremental() %}
    WHERE shift_day >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '2 months')::date
    {% endif %}
),

overtime AS (
    SELECT * FROM {{ ref('fct_overtime') }}

    {% if is_incremental() %}
    WHERE ot_date >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '2 months')::date
    {% endif %}
),

att_agg AS (
    SELECT
        tenant_id,
        employee_sk,
        EXTRACT(YEAR FROM shift_day)::smallint   AS year,
        EXTRACT(MONTH FROM shift_day)::smallint  AS month_number,
        TO_CHAR(shift_day, 'YYYY-MM')            AS year_month,

        COUNT(DISTINCT CASE WHEN NOT is_absent THEN shift_day END) AS days_present,
        COUNT(DISTINCT CASE WHEN is_absent THEN shift_day END)     AS days_absent,
        COUNT(DISTINCT CASE WHEN is_holiday AND worked_seconds > 0 THEN shift_day END)
            AS days_on_holiday_worked,
        COUNT(DISTINCT CASE WHEN late_seconds > 0 THEN shift_day END)        AS days_late,
        COUNT(DISTINCT CASE WHEN early_leave_seconds > 0 THEN shift_day END) AS days_early_leave,

        SUM(worked_hours)                              AS total_worked_hours,
        ROUND(SUM(late_seconds) / 60.0, 0)::integer   AS total_late_minutes,
        ROUND(SUM(early_leave_seconds) / 60.0, 0)::integer AS total_early_leave_minutes,

        COUNT(CASE WHEN is_manual_entry THEN 1 END)   AS manual_punch_count,
        COUNT(*)                                      AS total_attendance_rows
    FROM attendance
    WHERE employee_sk IS NOT NULL
    GROUP BY tenant_id, employee_sk,
        EXTRACT(YEAR FROM shift_day)::smallint,
        EXTRACT(MONTH FROM shift_day)::smallint,
        TO_CHAR(shift_day, 'YYYY-MM')
),

ot_agg AS (
    SELECT
        tenant_id,
        employee_sk,
        EXTRACT(YEAR FROM ot_date)::smallint   AS year,
        EXTRACT(MONTH FROM ot_date)::smallint AS month_number,
        SUM(total_ot_hours)                   AS total_overtime_hours
    FROM overtime
    WHERE employee_sk IS NOT NULL
    GROUP BY tenant_id, employee_sk,
        EXTRACT(YEAR FROM ot_date)::smallint,
        EXTRACT(MONTH FROM ot_date)::smallint
),

employee_ctx AS (
    SELECT
        employee_sk,
        tenant_id,
        emp_no,
        emp_fullname,
        legal_entity_name                       AS legal_entity,
        designation_name                        AS designation,
        grade_name                              AS grade
    FROM {{ ref('dim_employee') }}
    WHERE is_current = TRUE
),

final AS (
    SELECT
        a.tenant_id,
        a.employee_sk,
        a.year,
        a.month_number,
        a.year_month,

        e.emp_no,
        e.emp_fullname,
        e.legal_entity,
        e.designation,
        e.grade,

        a.days_present,
        a.days_absent,
        a.days_on_holiday_worked,
        a.days_late,
        a.days_early_leave,

        a.total_worked_hours,
        COALESCE(ot.total_overtime_hours, 0)   AS total_overtime_hours,
        a.total_late_minutes,
        a.total_early_leave_minutes,

        ROUND(
            a.days_present::numeric
                / NULLIF(a.days_present + a.days_absent, 0) * 100,
            2
        )                                       AS attendance_rate_pct,
        ROUND(
            (1.0 - (a.days_late::numeric / NULLIF(a.days_present, 0))) * 100,
            2
        )                                       AS punctuality_rate_pct,

        a.manual_punch_count,
        ROUND(
            a.manual_punch_count::numeric
                / NULLIF(a.total_attendance_rows, 0) * 100,
            2
        )                                       AS manual_punch_rate_pct,

        CURRENT_TIMESTAMP                       AS _refreshed_at

    FROM att_agg a
    LEFT JOIN ot_agg ot
        ON  ot.tenant_id    = a.tenant_id
        AND ot.employee_sk  = a.employee_sk
        AND ot.year         = a.year
        AND ot.month_number = a.month_number
    LEFT JOIN employee_ctx e
        ON  e.employee_sk   = a.employee_sk
        AND e.tenant_id     = a.tenant_id
)

SELECT * FROM final
