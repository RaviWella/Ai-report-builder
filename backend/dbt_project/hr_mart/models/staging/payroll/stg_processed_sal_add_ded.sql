-- Processed additions/deductions staging.

{{ config(materialized='view') }}

select
    '{{ target.name }}'::varchar(64)                       as tenant_id,
    '{{ var("source_system") }}'::varchar(32)              as source_system,
    ad.id                                                  as source_add_ded_id,
    ad.payroll_run_id,
    {{ payroll_run_group_id('ad.payroll_run_id') }}          as source_payroll_group_id,
    ad.employee_id                                         as source_emp_id,
    ad.proc_year                                           as processing_year,
    ad.proc_month                                          as processing_month,
    coalesce(ad.proc_half, 0)                              as processing_half,
    ad.proc_year,
    ad.proc_month,
    {{ payroll_period_label('ad.proc_year', 'ad.proc_month') }}
                                                           as period_label,
    ad.line_type,
    ad.line_type_name,
    ad.component_name,
    ad.amount,
    ad.is_epf_liable,
    case
        when ad.line_type in ('1', '3')
          or lower(coalesce(ad.line_type_name, '')) like '%addition%'
        then 'addition'
        else 'deduction'
    end                                                    as component_direction,
    coalesce(ad.updated_at, ad.created_at, now())          as _source_updated_at
from {{ source('payroll_processed', 'processed_sal_add_ded') }} ad
