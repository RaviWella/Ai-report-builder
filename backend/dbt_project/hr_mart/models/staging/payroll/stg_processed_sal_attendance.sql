-- Processed payroll attendance impact staging.

{{ config(materialized='view') }}

select
    '{{ target.name }}'::varchar(64)                       as tenant_id,
    '{{ var("source_system") }}'::varchar(32)              as source_system,
    sa.id                                                  as source_attendance_line_id,
    sa.payroll_run_id,
    {{ payroll_run_group_id('sa.payroll_run_id') }}          as source_payroll_group_id,
    sa.employee_id                                         as source_emp_id,
    sa.proc_year                                           as processing_year,
    sa.proc_month                                          as processing_month,
    coalesce(sa.proc_half, 0)                            as processing_half,
    sa.proc_year,
    sa.proc_month,
    {{ payroll_period_label('sa.proc_year', 'sa.proc_month') }}
                                                           as period_label,
    sa.line_type,
    sa.line_type_name,
    sa.amount,
    sa.value_text,
    coalesce(sa.updated_at, sa.created_at, now())          as _source_updated_at
from {{ source('payroll_processed', 'processed_sal_attendance') }} sa
