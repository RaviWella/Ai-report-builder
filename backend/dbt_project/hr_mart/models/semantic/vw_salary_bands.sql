-- vw_salary_bands — compensation bands by org slice (mart_salary_band_summary).

{{ config(materialized='view') }}

SELECT
    salary_band_sk,
    tenant_id,
    source_system,
    legal_entity_name,
    designation_name,
    grade_name,
    headcount,
    min_salary,
    max_salary,
    avg_salary,
    median_salary,
    payroll_cost,
    _refreshed_at
FROM {{ ref('mart_salary_band_summary') }}
