-- fact_attendance — daily attendance fact table
-- Grain: one row per employee per attendance date

{{
  config(
    materialized='table',
    unique_key='id'
  )
}}

WITH source AS (
    SELECT * FROM {{ source('hr_raw', 'stg_attendance') }}
),

emp_current AS (
    SELECT employee_sk, source_emp_id
    FROM {{ ref('dim_employee') }}
    WHERE is_current = TRUE
      AND tenant_id = '{{ target.name }}'
),

enriched AS (
    SELECT
        a.id,
        emp.employee_sk,
        a.employee_id                               AS source_emp_id,
        a.attendance_date,
        EXTRACT(YEAR FROM a.attendance_date)::INT   AS year,
        EXTRACT(MONTH FROM a.attendance_date)::INT  AS month,
        TO_CHAR(a.attendance_date, 'YYYY-MM')       AS period_label,
        a.check_in,
        a.check_out,
        a.status,
        a.late_minutes,
        a.early_leave_minutes,
        a.overtime_minutes,
        a.work_hours,
        a.shift_id,
        -- Derived flags
        CASE WHEN a.status = 'present' THEN 1 ELSE 0 END    AS is_present,
        CASE WHEN a.late_minutes > 0 THEN 1 ELSE 0 END      AS is_late,
        CASE WHEN a.overtime_minutes > 0 THEN 1 ELSE 0 END  AS has_overtime,
        ROUND(a.overtime_minutes::NUMERIC / 60, 2)           AS overtime_hours
    FROM source a
    LEFT JOIN emp_current emp ON emp.source_emp_id = a.employee_id
)

SELECT * FROM enriched
