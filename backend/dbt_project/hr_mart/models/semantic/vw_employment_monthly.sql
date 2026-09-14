-- vw_employment_monthly — tenant monthly workforce snapshot (mart_headcount_monthly).

{{ config(materialized='view') }}

SELECT
    tenant_id,
    source_system,
    TO_CHAR(snapshot_month, 'YYYY-MM')                  AS period_label,
    snapshot_month,
    active_headcount,
    resigned_headcount_eom,
    terminated_headcount_eom,
    other_non_active_headcount_eom,
    prior_month_active_headcount,
    net_active_headcount_change_mom,
    monthly_salary_cost_active,
    avg_years_of_service_active,
    fte_equivalent
FROM {{ ref('mart_headcount_monthly') }}
