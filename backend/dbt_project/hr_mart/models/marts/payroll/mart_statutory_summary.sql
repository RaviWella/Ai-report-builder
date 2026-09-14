-- Statutory reporting mart (§8.4).

{{ config(materialized='table', tags=['warehouse', 'warehouse_payroll', 'warehouse_marts']) }}

with salary as (
    select
        s.tenant_id,
        s.payroll_period_sk,
        e.legal_entity_name,
        sum(s.epf_employee_amount)                            as employee_epf,
        sum(s.epf_employer_amount)                            as employer_epf,
        sum(s.etf_amount)                                     as etf,
        sum(s.tax_amount)                                     as apit,
        sum(s.gross_salary)                                   as taxable_payroll,
        count(distinct s.employee_sk)                         as employee_count
    from {{ ref('fct_processed_salary') }} s
    left join {{ ref('dim_employee') }} e
        on e.employee_sk = s.employee_sk and e.is_current = true
    group by s.tenant_id, s.payroll_period_sk, e.legal_entity_name
)

select
    s.*,
    p.payroll_year,
    p.payroll_month,
    p.payroll_half,
    current_timestamp                                       as _refreshed_at
from salary s
left join {{ ref('dim_payroll_period') }} p
    on p.payroll_period_sk = s.payroll_period_sk
