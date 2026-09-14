-- fct_lieu_leave_entitlement — earned lieu leave entitlement events.

{{ config(
    materialized='table',
    tags=['leave', 'warehouse_marts'],
    indexes=[
        {'columns': ['tenant_id', 'employee_sk', 'calendar_date'], 'unique': false},
    ],
) }}

WITH src AS (
    SELECT * FROM {{ source('hr_raw', 'stg_lieu_leave_entitlement') }}
),

employee AS (
    SELECT
        employee_sk,
        tenant_id,
        source_emp_id,
        is_current,
        valid_from
    FROM {{ ref('dim_employee') }}
),

joined AS (
    SELECT
        '{{ target.name }}'::varchar(64)               AS tenant_id,
        '{{ var("source_system") }}'::varchar(32)      AS source_system,
        s.id                                           AS source_entitlement_id,
        emp.employee_sk,
        TO_CHAR(s.calendar_date, 'YYYYMMDD')::integer   AS calendar_date_sk,
        s.calendar_date,
        COALESCE(s.earned_days, 0)::numeric(8, 2)      AS earned_lieu_days,
        0::numeric(8, 2)                               AS adjusted_lieu_days,
        0::numeric(8, 2)                               AS paid_lieu_days,
        'attendance_holiday'::varchar(64)              AS earning_source,
        'earned'::varchar(64)                          AS earning_reason,
        s.final_status_code,
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
)

SELECT
    {{ dbt_utils.generate_surrogate_key([
        'tenant_id', 'source_system', 'source_entitlement_id'
    ]) }}                                              AS lieu_entitlement_sk,
    *
FROM joined
