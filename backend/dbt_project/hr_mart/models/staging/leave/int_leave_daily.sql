-- int_leave_daily — employee x leave date lines from application dates staging.

{{ config(materialized='view') }}

SELECT
    '{{ target.name }}'::varchar(64)                       AS tenant_id,
    '{{ var("source_system") }}'::varchar(32)              AS source_system,
    d.id                                                   AS source_leave_date_id,
    d.leave_application_id                                 AS source_application_id,
    'STANDARD'::varchar(32)                                AS leave_source_code,
    r.employee_id                                          AS source_emp_id,
    r.leave_type_id                                        AS source_leave_type_id,
    LOWER(TRIM(COALESCE(r.status, 'unknown')))             AS header_leave_status_code,
    d.leave_date,
    COALESCE(d.leave_day_count, 0)::numeric(8, 2)          AS leave_day_count,
    d.time_period,
    d.day_status                                           AS source_day_status,
    COALESCE(d.coverup_approved, 0) = 1                    AS coverup_approved,
    COALESCE(d.superior_approved, 0) = 1                   AS superior_approved,
    COALESCE(d.hr_approved, 0) = 1                         AS hr_approved,
    CASE
        WHEN COALESCE(d.time_period, 0) <> 0 THEN TRUE
        WHEN COALESCE(d.leave_day_count, 0) > 0
         AND COALESCE(d.leave_day_count, 0) < 1 THEN TRUE
        ELSE FALSE
    END                                                    AS is_half_day,
    CASE
        WHEN COALESCE(d.time_period, 0) = 1 THEN 'first_half'
        WHEN COALESCE(d.time_period, 0) = 2 THEN 'second_half'
        ELSE 'full_day'
    END                                                    AS half_day_type,
    COALESCE(d.updated_at, d.created_at, NOW())            AS _source_updated_at
FROM {{ source('hr_raw', 'stg_leave_application_dates') }} d
INNER JOIN {{ source('hr_raw', 'stg_leave_requests') }} r
    ON r.id = d.leave_application_id
WHERE d.id IS NOT NULL
  AND d.leave_date IS NOT NULL
  AND r.employee_id IS NOT NULL
