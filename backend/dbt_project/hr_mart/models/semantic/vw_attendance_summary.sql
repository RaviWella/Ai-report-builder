-- vw_attendance_summary — employee × month from mart_attendance_monthly_summary.

{{ config(materialized='view') }}

SELECT
    m.employee_sk,
    e.emp_section_id                                    AS department_id,
    e.branch_id,
    m.year_month                                        AS period_label,
    m.year::int                                         AS year,
    m.month_number::int                                 AS month,
    (m.days_present + m.days_absent)                    AS scheduled_days,
    m.days_present                                      AS present_days,
    m.days_late                                         AS late_count,
    CASE WHEN COALESCE(m.total_overtime_hours, 0) > 0 THEN 1 ELSE 0 END
                                                        AS overtime_days,
    COALESCE(m.total_overtime_hours, 0)                 AS overtime_hours,
    COALESCE(m.total_worked_hours, 0)                   AS avg_work_hours,
    COALESCE(m.total_late_minutes, 0)                   AS total_late_minutes
FROM {{ ref('mart_attendance_monthly_summary') }} m
JOIN {{ ref('dim_employee') }} e
    ON  e.employee_sk = m.employee_sk
    AND e.tenant_id = m.tenant_id
    AND e.is_current = TRUE
