-- vw_leave_utilization — leave utilization KPIs from monthly summary mart.

{{ config(materialized='view') }}

WITH monthly AS (
    SELECT *
    FROM {{ ref('mart_leave_monthly_summary') }}
    WHERE tenant_id = '{{ target.name }}'
),

balance_month AS (
    SELECT
        e.department_name,
        b.leave_type_sk,
        EXTRACT(YEAR FROM b.snapshot_date)::smallint   AS year,
        EXTRACT(MONTH FROM b.snapshot_date)::smallint  AS month_number,
        SUM(b.entitled_days)                           AS total_entitled_days,
        SUM(b.used_days)                               AS total_used_days,
        SUM(b.remaining_days)                          AS total_remaining_days
    FROM {{ ref('fct_leave_balance_snapshot') }} b
    INNER JOIN {{ ref('dim_employee') }} e
        ON e.employee_sk = b.employee_sk
       AND e.is_current = TRUE
    WHERE b.tenant_id = '{{ target.name }}'
      AND b.balance_source = 'hr_leave_balance'
    GROUP BY
        e.department_name,
        b.leave_type_sk,
        EXTRACT(YEAR FROM b.snapshot_date)::smallint,
        EXTRACT(MONTH FROM b.snapshot_date)::smallint
)

SELECT
    m.year_month,
    m.year,
    m.month_number,
    m.department_name,
    m.leave_type_name                               AS leave_type,
    m.leave_type_code,
    m.approved_leave_days,
    m.total_leave_days,
    m.pending_leave_days,
    m.employees_with_approved_leave                 AS employees_on_approved_leave,
    m.avg_approved_days_per_employee,
    bm.total_entitled_days,
    bm.total_used_days,
    bm.total_remaining_days,
    ROUND(
        m.approved_leave_days::numeric
            / NULLIF(bm.total_entitled_days, 0) * 100,
        2
    )                                               AS utilization_rate_pct,
    ROUND(
        m.approved_leave_days::numeric
            / NULLIF(m.approved_leave_days + COALESCE(bm.total_remaining_days, 0), 0)
            * 100,
        2
    )                                               AS period_usage_share_pct,
    m._refreshed_at
FROM monthly m
LEFT JOIN balance_month bm
    ON  bm.department_name = m.department_name
   AND bm.leave_type_sk IS NOT DISTINCT FROM m.leave_type_sk
   AND bm.year = m.year
   AND bm.month_number = m.month_number
