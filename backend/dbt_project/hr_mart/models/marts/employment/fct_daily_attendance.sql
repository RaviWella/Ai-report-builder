-- =============================================================================
-- fct_daily_attendance
-- Core attendance fact — one row per emp × shift_day × shift_order.
-- Incremental delete+insert for retroactive edits.
-- Joins dim_employee and dim_shift. LATERAL prefers PIT row for shift_day.
-- =============================================================================

{{ config(
    materialized='incremental',
    unique_key=['tenant_id', 'source_system', 'source_atten_id', 'shift_order'],
    incremental_strategy='delete+insert',
    on_schema_change='sync_all_columns',
    tags=['warehouse', 'warehouse_marts'],
    indexes=[
        {'columns': ['tenant_id', 'employee_sk', 'shift_day'], 'unique': false},
        {'columns': ['tenant_id', 'shift_day'], 'unique': false},
        {'columns': ['tenant_id', 'shift_day_date_sk'], 'unique': false}
    ]
) }}

WITH att AS (
    SELECT * FROM {{ ref('int_attendance_processed') }}

    {% if is_incremental() %}
    WHERE _source_updated_at >= (
        SELECT COALESCE(MAX(_source_updated_at), '1970-01-01'::timestamptz) - INTERVAL '1 hour'
        FROM {{ this }}
    )
    {% else %}
    WHERE shift_day >= '{{ var("attendance_start_date") }}'::date
    {% endif %}
),

employee AS (
    SELECT
        employee_sk,
        tenant_id,
        COALESCE(NULLIF(TRIM(source_system::text), ''), '{{ var("source_system") }}') AS source_system_norm,
        source_emp_id,
        valid_from,
        valid_to,
        is_current
    FROM {{ ref('dim_employee') }}
),

shift AS (
    SELECT
        shift_sk,
        tenant_id,
        COALESCE(NULLIF(TRIM(source_system::text), ''), '{{ var("source_system") }}') AS source_system_norm,
        source_shift_id,
        valid_from,
        valid_to,
        is_current
    FROM {{ ref('dim_shift') }}
),

dated AS (
    SELECT
        att.*,
        dd.date_sk AS shift_day_date_sk,
        COALESCE(NULLIF(TRIM(att.source_system), ''), '{{ var("source_system") }}') AS _source_system_norm
    FROM att
    LEFT JOIN {{ ref('dim_date') }} dd
        ON dd.calendar_date = att.shift_day
),

joined AS (
    SELECT
        att.tenant_id,
        att._source_system_norm                        AS source_system,
        att.source_atten_id,
        att.shift_order,

        emp.employee_sk,
        sh_actual.shift_sk,
        sh_planned.shift_sk                            AS planned_shift_sk,

        TO_CHAR(att.shift_day, 'YYYYMMDD')::integer   AS date_key,
        att.shift_day_date_sk,
        att.shift_day,

        att.punch_in_datetime,
        att.punch_out_datetime,
        att.punch_in_two_datetime,
        att.punch_out_two_datetime,

        att.worked_seconds,
        att.late_seconds,
        att.early_in_seconds,
        att.early_leave_seconds,
        att.overtime_seconds,

        ROUND(att.worked_seconds / 3600.0, 2)::numeric(6, 2)   AS worked_hours,
        ROUND(att.overtime_seconds / 3600.0, 2)::numeric(6, 2) AS overtime_hours,

        att.is_absent,
        att.is_holiday,
        att.holiday_name,
        att.holiday_type,
        att.is_weekend,
        att.worked_on_planned_shift,
        att.has_overtime,
        att.has_nopay,

        att.late_status,
        att.early_leave_status,
        att.ot_status,
        att.is_attendance_processed,
        att.is_salary_processed,
        att.is_approved,
        att.is_manual_entry,

        att.punch_in_location,
        att.punch_out_location,
        att.punch_in_latitude,
        att.punch_in_longitude,
        att.punch_out_latitude,
        att.punch_out_longitude,
        att.punch_in_branch,
        att.punch_out_branch,

        att.punch_in_requested_by,
        att.punch_out_requested_by,
        att.punch_in_approved_by,
        att.punch_out_approved_by,

        att.purpose,
        att.note,

        att._source_updated_at,
        CURRENT_TIMESTAMP                              AS _loaded_at

    FROM dated att

    LEFT JOIN LATERAL (
        SELECT e.employee_sk
        FROM employee e
        WHERE TRIM(e.tenant_id::text) = TRIM(att.tenant_id::text)
          AND e.source_system_norm = att._source_system_norm
          AND e.source_emp_id = att.source_emp_id
        ORDER BY
            CASE
                WHEN att.shift_day >= ((e.valid_from AT TIME ZONE 'UTC'))::date
                 AND att.shift_day < ((e.valid_to AT TIME ZONE 'UTC'))::date
                THEN 0 ELSE 1
            END,
            CASE WHEN e.is_current THEN 0 ELSE 1 END,
            e.valid_from DESC
        LIMIT 1
    ) emp ON TRUE

    LEFT JOIN LATERAL (
        SELECT s.shift_sk
        FROM shift s
        WHERE TRIM(s.tenant_id::text) = TRIM(att.tenant_id::text)
          AND s.source_system_norm = att._source_system_norm
          AND att.ref_shift_id IS NOT NULL
          AND s.source_shift_id = att.ref_shift_id
        ORDER BY
            CASE
                WHEN att.shift_day >= ((s.valid_from AT TIME ZONE 'UTC'))::date
                 AND att.shift_day < ((s.valid_to AT TIME ZONE 'UTC'))::date
                THEN 0 ELSE 1
            END,
            CASE WHEN s.is_current THEN 0 ELSE 1 END,
            s.valid_from DESC
        LIMIT 1
    ) sh_actual ON TRUE

    LEFT JOIN LATERAL (
        SELECT s.shift_sk
        FROM shift s
        WHERE TRIM(s.tenant_id::text) = TRIM(att.tenant_id::text)
          AND s.source_system_norm = att._source_system_norm
          AND att.planned_shift_id IS NOT NULL
          AND s.source_shift_id = att.planned_shift_id
        ORDER BY
            CASE
                WHEN att.shift_day >= ((s.valid_from AT TIME ZONE 'UTC'))::date
                 AND att.shift_day < ((s.valid_to AT TIME ZONE 'UTC'))::date
                THEN 0 ELSE 1
            END,
            CASE WHEN s.is_current THEN 0 ELSE 1 END,
            s.valid_from DESC
        LIMIT 1
    ) sh_planned ON TRUE
),

final AS (
    SELECT
        j.*,
        ROW_NUMBER() OVER (
            PARTITION BY j.tenant_id, j.source_system, j.source_atten_id, j.shift_order
            ORDER BY
                j.employee_sk NULLS LAST,
                j.shift_sk NULLS LAST,
                j.planned_shift_sk NULLS LAST,
                j._source_updated_at DESC NULLS LAST
        ) AS _grain_rn
    FROM joined j
)

SELECT
    tenant_id,
    source_system,
    source_atten_id,
    shift_order,
    employee_sk,
    shift_sk,
    planned_shift_sk,
    date_key,
    shift_day_date_sk,
    shift_day,
    punch_in_datetime,
    punch_out_datetime,
    punch_in_two_datetime,
    punch_out_two_datetime,
    worked_seconds,
    late_seconds,
    early_in_seconds,
    early_leave_seconds,
    overtime_seconds,
    worked_hours,
    overtime_hours,
    is_absent,
    is_holiday,
    holiday_name,
    holiday_type,
    is_weekend,
    worked_on_planned_shift,
    has_overtime,
    has_nopay,
    late_status,
    early_leave_status,
    ot_status,
    is_attendance_processed,
    is_salary_processed,
    is_approved,
    is_manual_entry,
    punch_in_location,
    punch_out_location,
    punch_in_latitude,
    punch_in_longitude,
    punch_out_latitude,
    punch_out_longitude,
    punch_in_branch,
    punch_out_branch,
    punch_in_requested_by,
    punch_out_requested_by,
    punch_in_approved_by,
    punch_out_approved_by,
    purpose,
    note,
    _source_updated_at,
    _loaded_at
FROM final
WHERE _grain_rn = 1
