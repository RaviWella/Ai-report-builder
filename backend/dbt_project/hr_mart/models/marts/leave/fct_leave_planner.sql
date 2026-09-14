-- fct_leave_planner — planned leave vs actual utilization.

{{ config(
    materialized='table',
    tags=['leave', 'warehouse_marts'],
    indexes=[
        {'columns': ['tenant_id', 'employee_sk', 'planned_start_date'], 'unique': false},
    ],
) }}

WITH planner AS (
    SELECT * FROM {{ source('hr_raw', 'stg_leave_planner') }}
),

employee AS (
    SELECT employee_sk, tenant_id, source_emp_id, is_current, valid_from
    FROM {{ ref('dim_employee') }}
),

leave_type AS (
    SELECT leave_type_sk, tenant_id, source_leave_type_id, is_current, valid_from
    FROM {{ ref('dim_leave_type') }}
),

actual AS (
    SELECT
        employee_sk,
        source_emp_id,
        leave_application_sk,
        start_date,
        end_date,
        approved_days,
        leave_source_code
    FROM {{ ref('fct_leave_application') }}
    WHERE leave_source_code IN ('STANDARD', 'PLANNER')
      AND leave_status_code = 'approved'
),

joined AS (
    SELECT
        '{{ target.name }}'::varchar(64)               AS tenant_id,
        '{{ var("source_system") }}'::varchar(32)      AS source_system,
        p.id                                           AS source_planner_id,
        emp.employee_sk,
        lt.leave_type_sk,
        act.leave_application_sk                       AS actual_leave_application_sk,
        TO_CHAR(p.planned_start_date, 'YYYYMMDD')::integer AS planned_start_date_sk,
        TO_CHAR(p.planned_end_date, 'YYYYMMDD')::integer AS planned_end_date_sk,
        p.planned_start_date,
        p.planned_end_date,
        COALESCE(p.planned_days, 0)::numeric(8, 2)       AS planned_days,
        COALESCE(act.approved_days, 0)::numeric(8, 2)    AS utilized_days,
        (COALESCE(p.planned_days, 0) - COALESCE(act.approved_days, 0))::numeric(8, 2)
                                                       AS variance_days,
        LOWER(TRIM(COALESCE(p.planner_status, 'unknown'))) AS planner_status,
        p.purpose                                      AS planner_purpose,
        COALESCE(p.updated_at, p.created_at, NOW())    AS _source_updated_at,
        CURRENT_TIMESTAMP                              AS _loaded_at
    FROM planner p
    LEFT JOIN LATERAL (
        SELECT e.employee_sk
        FROM employee e
        WHERE TRIM(e.tenant_id::text) = '{{ target.name }}'
          AND e.source_emp_id = p.employee_id
        ORDER BY CASE WHEN e.is_current THEN 0 ELSE 1 END, e.valid_from DESC
        LIMIT 1
    ) emp ON TRUE
    LEFT JOIN LATERAL (
        SELECT t.leave_type_sk
        FROM leave_type t
        WHERE TRIM(t.tenant_id::text) = '{{ target.name }}'
          AND p.leave_type_id IS NOT NULL
          AND t.source_leave_type_id = p.leave_type_id
        ORDER BY CASE WHEN t.is_current THEN 0 ELSE 1 END, t.valid_from DESC
        LIMIT 1
    ) lt ON TRUE
    LEFT JOIN LATERAL (
        SELECT a.leave_application_sk, a.approved_days
        FROM actual a
        WHERE a.source_emp_id = p.employee_id
          AND a.start_date <= p.planned_end_date
          AND a.end_date >= p.planned_start_date
        ORDER BY a.approved_days DESC NULLS LAST
        LIMIT 1
    ) act ON TRUE
)

SELECT
    {{ dbt_utils.generate_surrogate_key([
        'tenant_id', 'source_system', 'source_planner_id'
    ]) }}                                              AS leave_planner_sk,
    *
FROM joined
