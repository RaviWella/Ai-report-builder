{{ config(materialized='view') }}

select
    '{{ target.name }}'::varchar(64)                       as tenant_id,
    '{{ var("source_system") }}'::varchar(32)              as source_system,
    n.id                                                   as source_variable_item_id,
    n.payroll_run_id,
    {{ payroll_run_group_id('n.payroll_run_id') }}           as source_payroll_group_id,
    n.employee_id                                          as source_emp_id,
    cast(null as integer)                                  as source_component_id,
    n.proc_year                                            as processing_year,
    n.proc_month                                           as processing_month,
    coalesce(n.proc_half, 0)                               as processing_half,
    n.proc_year,
    n.proc_month,
    {{ payroll_period_label('n.proc_year', 'n.proc_month') }} as period_label,
    coalesce(n.item_name, 'non_consider_item')               as item_name,
    'non_consider'::varchar(16)                            as item_direction,
    n.amount,
    coalesce(n.is_considered_for_payroll, false)           as is_considered_for_payroll,
    coalesce(n.updated_at, n.created_at, now())            as _source_updated_at
from {{ source('payroll_processed', 'processed_non_consider_pay_items') }} n
