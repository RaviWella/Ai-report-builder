{{ config(materialized='view') }}

select
    '{{ target.name }}'::varchar(64)                       as tenant_id,
    '{{ var("source_system") }}'::varchar(32)              as source_system,
    m.id                                                   as source_multi_currency_id,
    m.payroll_run_id,
    {{ payroll_run_group_id('m.payroll_run_id') }}           as source_payroll_group_id,
    m.employee_id                                          as source_emp_id,
    m.source_currency,
    m.target_currency,
    m.exchange_rate,
    m.salary_amount,
    m.converted_amount,
    m.proc_year                                            as processing_year,
    m.proc_month                                           as processing_month,
    coalesce(m.proc_half, 0)                               as processing_half,
    {{ payroll_period_label('m.proc_year', 'm.proc_month') }} as period_label,
    coalesce(m.updated_at, m.created_at, now())            as _source_updated_at
from {{ source('payroll_processed', 'processed_multi_currency_for_emp_sal') }} m
