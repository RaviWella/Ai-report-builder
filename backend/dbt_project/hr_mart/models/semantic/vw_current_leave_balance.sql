-- vw_current_leave_balance — AI-safe current leave balances (latest snapshot).

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
)

SELECT
    e.emp_no                                        AS employee_number,
    e.emp_fullname                                  AS employee_name,
    e.department_name                               AS department_name,
    COALESCE(lt.leave_type_name, b.leave_type_name) AS leave_type,
    lt.leave_type_code,
    b.entitlement_year,
    b.entitled_days,
    b.used_days,
    b.remaining_days,
    b.pending_approval_days,
    b.period_start_date,
    b.period_end_date,
    b.snapshot_date
FROM current_balances b
INNER JOIN {{ ref('dim_employee') }} e
    ON e.employee_sk = b.employee_sk
   AND e.is_current = TRUE
LEFT JOIN {{ ref('dim_leave_type') }} lt
    ON lt.leave_type_sk = b.leave_type_sk
   AND lt.is_current = TRUE
