-- int_leave_balance_snapshot — unified balance rows from HR balance + payroll entitlement staging.

{{ config(materialized='view') }}

WITH hr_balance AS (
    SELECT
        '{{ target.name }}'::varchar(64)                   AS tenant_id,
        '{{ var("source_system") }}'::varchar(32)          AS source_system,
        'hr_leave_balance'::varchar(32)                    AS balance_source,
        b.id                                               AS source_balance_id,
        b.employee_id                                      AS source_emp_id,
        b.leave_type_id                                    AS source_leave_type_id,
        b.leave_type_name,
        COALESCE(b.entitled_days, 0)::numeric(10, 2)       AS entitled_days,
        COALESCE(b.used_days, 0)::numeric(10, 2)           AS used_days,
        COALESCE(b.remaining_days, 0)::numeric(10, 2)       AS remaining_days,
        COALESCE(b.pending_approval_days, 0)::numeric(10, 2) AS pending_approval_days,
        0::numeric(10, 2)                                  AS earned_days,
        0::numeric(10, 2)                                  AS carry_forward_days,
        0::numeric(10, 2)                                  AS encashed_days,
        0::numeric(10, 2)                                  AS expired_days,
        b.entitlement_year,
        b.period_start_date,
        b.period_end_date,
        'current'::varchar(32)                             AS balance_status,
        COALESCE(b.updated_at, b.created_at, NOW())        AS _source_updated_at
    FROM {{ source('hr_raw', 'stg_leave_balance') }} b
    WHERE b.employee_id IS NOT NULL
),

payroll_entitlement AS (
    SELECT
        '{{ target.name }}'::varchar(64)                   AS tenant_id,
        '{{ var("source_system") }}'::varchar(32)          AS source_system,
        'prl_leaveentitle'::varchar(32)                    AS balance_source,
        e.id                                               AS source_balance_id,
        e.employee_id                                      AS source_emp_id,
        e.leave_type_id                                    AS source_leave_type_id,
        NULL::varchar(255)                                 AS leave_type_name,
        COALESCE(e.entitled_days, 0)::numeric(10, 2)       AS entitled_days,
        0::numeric(10, 2)                                  AS used_days,
        COALESCE(e.entitled_days, 0)::numeric(10, 2)       AS remaining_days,
        0::numeric(10, 2)                                  AS pending_approval_days,
        COALESCE(e.entitled_days, 0)::numeric(10, 2)       AS earned_days,
        0::numeric(10, 2)                                  AS carry_forward_days,
        0::numeric(10, 2)                                  AS encashed_days,
        0::numeric(10, 2)                                  AS expired_days,
        e.entitlement_year,
        e.period_start_date,
        e.period_end_date,
        CASE
            WHEN COALESCE(e.status_code, 0) = 1 THEN 'active'
            ELSE 'inactive'
        END                                                AS balance_status,
        COALESCE(e.updated_at, e.created_at, NOW())        AS _source_updated_at
    FROM {{ source('hr_raw', 'stg_leave_entitlement') }} e
    WHERE e.employee_id IS NOT NULL
)

SELECT * FROM hr_balance
UNION ALL
SELECT * FROM payroll_entitlement
