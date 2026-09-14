{{ config(materialized='view') }}

select
    '{{ target.name }}'::varchar(64)                       as tenant_id,
    '{{ var("source_system") }}'::varchar(32)              as source_system,
    r.id                                                   as source_salary_retrieve_id,
    r.payroll_run_id,
    {{ payroll_run_group_id('r.payroll_run_id') }}           as source_payroll_group_id,
    r.employee_id                                          as source_emp_id,
    coalesce(r.is_bank, false)                             as is_bank,
    r.proc_year                                            as processing_year,
    r.proc_month                                           as processing_month,
    coalesce(r.proc_half, 0)                               as processing_half,
    coalesce(r.updated_at, r.created_at, now())            as _source_updated_at
from {{ source('payroll_processed', 'prl_salary_retrieve') }} r
where r.id is not null
