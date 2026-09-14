-- fct_maternity_leave — one row per maternity leave request.

{{ config(
    materialized='table',
    tags=['leave', 'warehouse_marts'],
    indexes=[
        {'columns': ['tenant_id', 'employee_sk'], 'unique': false},
    ],
) }}

WITH src AS (
    SELECT * FROM {{ source('hr_raw', 'stg_maternity_leave') }}
),

employee AS (
    SELECT employee_sk, tenant_id, source_emp_id, is_current, valid_from
    FROM {{ ref('dim_employee') }}
),

leave_type AS (
    SELECT leave_type_sk, tenant_id, source_leave_type_id, is_current, valid_from
    FROM {{ ref('dim_leave_type') }}
),

joined AS (
    SELECT
        '{{ target.name }}'::varchar(64)               AS tenant_id,
        '{{ var("source_system") }}'::varchar(32)      AS source_system,
        s.id                                           AS source_maternity_leave_id,
        emp.employee_sk,
        lt.leave_type_sk,
        TO_CHAR(s.start_date, 'YYYYMMDD')::integer     AS maternity_start_date_sk,
        TO_CHAR(COALESCE(s.end_date, s.expected_end_date), 'YYYYMMDD')::integer
                                                       AS maternity_end_date_sk,
        s.start_date                                   AS maternity_start_date,
        COALESCE(s.end_date, s.expected_end_date)        AS maternity_end_date,
        s.expected_end_date                            AS expected_delivery_date,
        GREATEST(
            (COALESCE(s.end_date, s.expected_end_date, s.start_date) - s.start_date) + 1,
            0
        )::numeric(8, 2)                               AS maternity_days,
        0::numeric(8, 2)                               AS feeding_hours_allocated,
        0::numeric(8, 2)                               AS feeding_hours_used,
        COALESCE(s.child_count, 0) > 0                 AS feeding_hours_eligible_flag,
        LOWER(TRIM(COALESCE(s.status, 'unknown')))      AS maternity_status_code,
        s.purpose                                      AS maternity_purpose,
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
)

SELECT
    {{ dbt_utils.generate_surrogate_key([
        'tenant_id', 'source_system', 'source_maternity_leave_id'
    ]) }}                                              AS maternity_leave_sk,
    *
FROM joined
