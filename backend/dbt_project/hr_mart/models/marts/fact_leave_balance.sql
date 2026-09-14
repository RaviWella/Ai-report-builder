-- fact_leave_balance — legacy compatibility layer over fct_leave_application.
-- Preserves Phase-0 column contract for vw_leave_summary and existing reports.

{{
  config(
    materialized='table',
    unique_key='id',
    tags=['leave', 'warehouse_marts'],
  )
}}

WITH apps AS (
    SELECT *
    FROM {{ ref('fct_leave_application') }}
    WHERE leave_status_code = 'approved'
),

types AS (
    SELECT
        leave_type_sk,
        source_leave_type_id,
        leave_type_code,
        leave_type_name,
        is_paid_leave,
        max_carry_forward_days
    FROM {{ ref('dim_leave_type') }}
    WHERE is_current = TRUE
      AND tenant_id = '{{ target.name }}'
)

SELECT
    a.source_application_id                       AS id,
    a.employee_sk,
    a.source_emp_id,
    a.source_leave_type_id                          AS leave_type_id,
    t.leave_type_code,
    t.leave_type_name,
    COALESCE(t.is_paid_leave, TRUE)               AS is_paid,
    TO_CHAR(a.start_date, 'YYYY-MM')                AS period_label,
    EXTRACT(YEAR FROM a.start_date)::INT            AS year,
    a.requested_days                                AS days_requested,
    a.approved_days                                 AS days_approved,
    t.max_carry_forward_days                        AS days_entitled,
    COALESCE(t.max_carry_forward_days, 0)
        - COALESCE(a.approved_days, 0)              AS balance_days,
    CASE
        WHEN LOWER(COALESCE(t.leave_type_code, '')) LIKE '%sick%'
          OR LOWER(COALESCE(t.leave_type_name, '')) LIKE '%sick%'
        THEN a.approved_days
        ELSE 0::numeric(8, 2)
    END                                             AS sick_days
FROM apps a
LEFT JOIN types t
    ON t.source_leave_type_id = a.source_leave_type_id
   AND t.leave_type_sk = a.leave_type_sk
