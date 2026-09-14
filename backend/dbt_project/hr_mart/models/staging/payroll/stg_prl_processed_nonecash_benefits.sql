{{ config(materialized='view') }}

select
    '{{ target.name }}'::varchar(64)                       as tenant_id,
    '{{ var("source_system") }}'::varchar(32)              as source_system,
    nb.id                                                  as source_noncash_benefit_id,
    nb.payroll_run_id,
    {{ payroll_run_group_id('nb.payroll_run_id') }}          as source_payroll_group_id,
    nb.employee_id                                         as source_emp_id,
    nb.benefit_name,
    nb.benefit_type,
    nb.benefit_value,
    nb.taxable_value,
    nb.proc_year                                           as processing_year,
    nb.proc_month                                          as processing_month,
    coalesce(nb.proc_half, 0)                              as processing_half,
    {{ payroll_period_label('nb.proc_year', 'nb.proc_month') }} as period_label,
    coalesce(nb.updated_at, nb.created_at, now())          as _source_updated_at
from {{ source('payroll_processed', 'prl_processed_nonecash_benefits') }} nb
