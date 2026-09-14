-- =============================================================================
-- mart_salary_band_summary
-- Compensation benchmarking by org slice (current active employees).
-- Uses dim_employee current salary; optional cross-check with fct_salary_change.
-- Grain: tenant × legal entity × designation × grade.
-- =============================================================================

{{ config(
    materialized='table',
    tags=['warehouse', 'warehouse_marts'],
    indexes=[
        {'columns': ['tenant_id', 'legal_entity_name', 'designation_name', 'grade_name'], 'unique': true}
    ]
) }}

with active_employees as (
    select
        tenant_id,
        source_system,
        legal_entity_name,
        designation_name,
        grade_name,
        employee_category,
        basic_salary::numeric(14, 2)              as basic_salary
    from {{ ref('dim_employee') }}
    where is_current = true
      and emp_status = 'active'
      and basic_salary is not null
),

band_stats as (
    select
        tenant_id,
        source_system,
        coalesce(legal_entity_name, 'Unknown')    as legal_entity_name,
        coalesce(designation_name, 'Unknown')     as designation_name,
        coalesce(grade_name, 'Unknown')           as grade_name,

        count(*)                                  as headcount,
        min(basic_salary)                         as min_salary,
        max(basic_salary)                         as max_salary,
        round(avg(basic_salary)::numeric, 2)      as avg_salary,
        round(
            (percentile_cont(0.5) within group (order by basic_salary))::numeric,
            2
        )                                         as median_salary,
        round(sum(basic_salary)::numeric, 2)      as payroll_cost

    from active_employees
    group by 1, 2, 3, 4, 5
)

select
    {{ dbt_utils.generate_surrogate_key([
        'tenant_id', 'source_system', 'legal_entity_name', 'designation_name', 'grade_name'
    ]) }}                                       as salary_band_sk,

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
    current_timestamp                           as _refreshed_at

from band_stats
