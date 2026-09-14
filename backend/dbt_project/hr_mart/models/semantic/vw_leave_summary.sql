-- vw_leave_summary — AI-safe leave aggregation view

{{
  config(materialized='view')
}}

SELECT
    l.employee_sk,
    e.department_id,
    e.branch_id,
    l.period_label,
    l.year,
    l.leave_type_code,
    l.leave_type_name,
    l.is_paid,
    l.days_approved                                 AS days_taken,
    l.days_entitled,
    l.balance_days,
    l.sick_days
FROM {{ ref('fact_leave_balance') }} l
JOIN {{ ref('dim_employee') }} e ON e.employee_sk = l.employee_sk
