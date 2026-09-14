-- Total workforce compensation / CTC mart (§8.5).

{{ config(materialized='table', tags=['warehouse', 'warehouse_payroll', 'warehouse_marts']) }}

with salary as (
    select * from {{ ref('fct_processed_salary') }}
),

noncash as (
    select
        tenant_id,
        employee_sk,
        payroll_period_sk,
        sum(benefit_value)                                    as non_cash_benefits
    from {{ ref('fct_noncash_benefit') }}
    group by 1, 2, 3
)

select
    s.tenant_id,
    s.employee_sk,
    s.payroll_period_sk,
    s.basic_salary,
    s.epf_employer_amount                                   as employer_epf,
    s.etf_amount                                            as etf,
    s.bonus_amount                                          as bonuses,
    s.ot_amount                                             as ot,
    coalesce(nc.non_cash_benefits, 0)                       as non_cash_benefits,
    coalesce(s.basic_salary, 0)
        + coalesce(s.epf_employer_amount, 0)
        + coalesce(s.etf_amount, 0)
        + coalesce(s.bonus_amount, 0)
        + coalesce(s.ot_amount, 0)
        + coalesce(nc.non_cash_benefits, 0)                 as total_compensation,
    current_timestamp                                       as _refreshed_at
from salary s
left join noncash nc
    on nc.tenant_id = s.tenant_id
   and nc.employee_sk = s.employee_sk
   and nc.payroll_period_sk = s.payroll_period_sk
