-- int_attendance_processed — normalized attendance rows from stg_attendance.
-- Maps MintHRM HR_ATTEDANCE staging into the warehouse attendance contract.

{{ config(materialized='view') }}

SELECT
    '{{ target.name }}'::varchar(64)                   AS tenant_id,
    '{{ var("source_system") }}'::varchar(32)           AS source_system,
    a.id                                              AS source_atten_id,
    1                                                 AS shift_order,
    a.employee_id                                     AS source_emp_id,
    a.attendance_date                                 AS shift_day,
    a.shift_id                                        AS ref_shift_id,
    a.shift_id                                        AS planned_shift_id,

    a.check_in                                        AS punch_in_datetime,
    a.check_out                                       AS punch_out_datetime,
    NULL::timestamptz                                 AS punch_in_two_datetime,
    NULL::timestamptz                                 AS punch_out_two_datetime,

    COALESCE(ROUND(a.work_hours * 3600)::bigint, 0)     AS worked_seconds,
    COALESCE(a.late_minutes, 0) * 60                    AS late_seconds,
    0                                                 AS early_in_seconds,
    COALESCE(a.early_leave_minutes, 0) * 60             AS early_leave_seconds,
    COALESCE(a.overtime_minutes, 0) * 60                AS overtime_seconds,

    (LOWER(COALESCE(a.status, '')) <> 'present')        AS is_absent,
    FALSE                                             AS is_holiday,
    NULL::varchar(255)                                AS holiday_name,
    NULL::varchar(64)                                 AS holiday_type,
    (EXTRACT(DOW FROM a.attendance_date) IN (0, 6))     AS is_weekend,
    (LOWER(COALESCE(a.status, '')) = 'present')          AS worked_on_planned_shift,
    (COALESCE(a.overtime_minutes, 0) > 0)               AS has_overtime,
    FALSE                                             AS has_nopay,

    CASE WHEN COALESCE(a.late_minutes, 0) > 0 THEN 'late' ELSE NULL END
                                                      AS late_status,
    CASE WHEN COALESCE(a.early_leave_minutes, 0) > 0 THEN 'early_leave' ELSE NULL END
                                                      AS early_leave_status,
    CASE WHEN COALESCE(a.overtime_minutes, 0) > 0 THEN 'ot' ELSE NULL END
                                                      AS ot_status,
    TRUE                                              AS is_attendance_processed,
    FALSE                                             AS is_salary_processed,
    TRUE                                              AS is_approved,
    FALSE                                             AS is_manual_entry,

    NULL::varchar(255)                                AS punch_in_location,
    NULL::varchar(255)                                AS punch_out_location,
    NULL::numeric(12, 8)                              AS punch_in_latitude,
    NULL::numeric(12, 8)                              AS punch_in_longitude,
    NULL::numeric(12, 8)                              AS punch_out_latitude,
    NULL::numeric(12, 8)                              AS punch_out_longitude,
    NULL::varchar(128)                                AS punch_in_branch,
    NULL::varchar(128)                                AS punch_out_branch,

    NULL::integer                                     AS punch_in_requested_by,
    NULL::integer                                     AS punch_out_requested_by,
    NULL::integer                                     AS punch_in_approved_by,
    NULL::integer                                     AS punch_out_approved_by,

    NULL::varchar(255)                                AS purpose,
    NULL::text                                        AS note,

    COALESCE(a.updated_at, a.created_at, NOW())       AS _source_updated_at

FROM {{ source('hr_raw', 'stg_attendance') }} a
WHERE a.employee_id IS NOT NULL
  AND a.attendance_date IS NOT NULL
