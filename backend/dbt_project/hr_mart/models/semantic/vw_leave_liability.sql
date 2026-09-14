-- vw_leave_liability — payroll liability / expiring paid leave (latest snapshot).

{{ config(materialized='view') }}

WITH latest_snapshot AS (
    SELECT MAX(snapshot_date) AS snapshot_date
    FROM {{ ref('fct_leave_balance_snapshot') }}
    WHERE tenant_id = '{{ target.name }}'
),

current_balances AS (
    SELECT b.*
    FROM {{ ref('fct_leave_balance_snapshot') }} b
    INNER JOIN latest_snapshot ls
        ON b.snapshot_date = ls.snapshot_date
    WHERE b.tenant_id = '{{ target.name }}'
      AND b.balance_source = 'hr_leave_balance'
      AND COALESCE(b.remaining_days, 0) > 0
)

SELECT
    e.emp_no                                        AS employee_number,
    e.emp_fullname                                  AS employee_name,
    e.department_name                               AS department_name,
    e.legal_entity_name                             AS legal_entity,
    COALESCE(lt.leave_type_name, b.leave_type_name) AS leave_type,
    lt.leave_type_code,
    COALESCE(lt.is_paid_leave, TRUE)                AS is_paid_leave,
    b.entitlement_year,
    b.entitled_days,
    b.used_days,
    b.remaining_days                                AS liability_days,
    b.carry_forward_days,
    b.expired_days,
    b.pending_approval_days,
    b.period_start_date,
    b.period_end_date                               AS expiry_date,
    CASE
        WHEN b.period_end_date IS NOT NULL
        THEN (b.period_end_date - CURRENT_DATE)
        ELSE NULL
    END                                             AS days_until_expiry,
    CASE
        WHEN b.period_end_date IS NOT NULL
         AND b.period_end_date <= CURRENT_DATE + INTERVAL '90 days'
        THEN TRUE
        ELSE FALSE
    END                                             AS is_expiring_within_90_days,
    b.snapshot_date
FROM current_balances b
INNER JOIN {{ ref('dim_employee') }} e
    ON e.employee_sk = b.employee_sk
   AND e.is_current = TRUE
LEFT JOIN {{ ref('dim_leave_type') }} lt
    ON lt.leave_type_sk = b.leave_type_sk
   AND lt.is_current = TRUE
WHERE COALESCE(lt.is_paid_leave, TRUE) = TRUE
