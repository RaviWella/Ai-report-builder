-- fct_short_leave_usage — one row per short leave request.

{{ config(
    materialized='table',
    tags=['leave', 'warehouse_marts'],
    indexes=[
        {'columns': ['tenant_id', 'employee_sk', 'short_leave_date'], 'unique': false},
    ],
) }}

WITH src AS (
    SELECT * FROM {{ source('hr_raw', 'stg_short_leave') }}
),

employee AS (
    SELECT
        employee_sk,
        tenant_id,
        COALESCE(NULLIF(TRIM(source_system::text), ''), '{{ var("source_system") }}')
                                                    AS source_system_norm,
        source_emp_id,
        valid_from,
        valid_to,
        is_current
    FROM {{ ref('dim_employee') }}
),

leave_type AS (
    SELECT
        leave_type_sk,
        tenant_id,
        COALESCE(NULLIF(TRIM(source_system::text), ''), '{{ var("source_system") }}')
                                                    AS source_system_norm,
        source_leave_type_id,
        valid_from,
        valid_to,
        is_current
    FROM {{ ref('dim_leave_type') }}
),

joined AS (
    SELECT
        '{{ target.name }}'::varchar(64)               AS tenant_id,
        '{{ var("source_system") }}'::varchar(32)      AS source_system,
        s.id                                           AS source_short_leave_id,
        emp.employee_sk,
        lt.leave_type_sk,
        ded.leave_type_sk                              AS deduction_leave_type_sk,
        TO_CHAR(s.short_leave_date, 'YYYYMMDD')::integer AS request_date_sk,
        s.short_leave_date,
        s.start_time,
        s.end_time,
        COALESCE(s.duration_hours, 0)::numeric(8, 2)   AS short_leave_hours,
        CASE
            WHEN LOWER(TRIM(COALESCE(s.status, ''))) = 'approved'
            THEN GREATEST(COALESCE(s.duration_hours, 0) / 8.0, 0.125)::numeric(8, 2)
            ELSE 0::numeric(8, 2)
        END                                            AS deducted_leave_days,
        s.time_category                                AS duration_category,
        s.time_category                                AS time_category,
        LOWER(TRIM(COALESCE(s.status, 'unknown')))      AS short_leave_status_code,
        s.purpose,
        COALESCE(s.updated_at, s.created_at, NOW())    AS _source_updated_at,
        CURRENT_TIMESTAMP                              AS _loaded_at
    FROM src s
    LEFT JOIN LATERAL (
        SELECT e.employee_sk
        FROM employee e
        WHERE TRIM(e.tenant_id::text) = '{{ target.name }}'
          AND e.source_emp_id = s.employee_id
        ORDER BY CASE WHEN e.is_current THEN 0 ELSE 1 END, e.valid_from DESC
        LIMIT 1
    ) emp ON TRUE
    LEFT JOIN LATERAL (
        SELECT t.leave_type_sk
        FROM leave_type t
        WHERE TRIM(t.tenant_id::text) = '{{ target.name }}'
          AND s.leave_type_id IS NOT NULL
          AND t.source_leave_type_id = s.leave_type_id
        ORDER BY CASE WHEN t.is_current THEN 0 ELSE 1 END, t.valid_from DESC
        LIMIT 1
    ) lt ON TRUE
    LEFT JOIN LATERAL (
        SELECT t.leave_type_sk
        FROM leave_type t
        WHERE TRIM(t.tenant_id::text) = '{{ target.name }}'
          AND s.deducted_leave_type_id IS NOT NULL
          AND t.source_leave_type_id = s.deducted_leave_type_id
        ORDER BY CASE WHEN t.is_current THEN 0 ELSE 1 END, t.valid_from DESC
        LIMIT 1
    ) ded ON TRUE
)

SELECT
    {{ dbt_utils.generate_surrogate_key([
        'tenant_id', 'source_system', 'source_short_leave_id'
    ]) }}                                              AS short_leave_sk,
    *
FROM joined
