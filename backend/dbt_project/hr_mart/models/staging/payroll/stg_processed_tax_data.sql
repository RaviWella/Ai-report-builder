{{ config(materialized='view') }}

select
    '{{ target.name }}'::varchar(64)                       as tenant_id,
    '{{ var("source_system") }}'::varchar(32)              as source_system,
    t.id                                                   as source_tax_id,
    t.payroll_run_id,
    {{ payroll_run_group_id('t.payroll_run_id') }}           as source_payroll_group_id,
    t.employee_id                                          as source_emp_id,
    t.proc_year                                            as processing_year,
    t.proc_month                                           as processing_month,
    coalesce(t.proc_half, 0)                               as processing_half,
    t.proc_year,
    t.proc_month,
    {{ payroll_period_label('t.proc_year', 't.proc_month') }} as period_label,
    t.tax_component_code,
    t.tax_component_name,
    t.tax_amount,
    t.taxable_amount,
    coalesce(t.tax_relief_amount, 0)                       as tax_relief_amount,
    coalesce(t.tax_percentage, 0)                          as tax_percentage,
    coalesce(t.annualized_taxable_income, t.taxable_amount * 12, 0)
                                                           as annualized_taxable_income,
    coalesce(t.updated_at, t.created_at, now())            as _source_updated_at
from {{ source('payroll_processed', 'processed_tax_data_for_employee') }} t
