{{ config(materialized='view') }}

select
    '{{ target.name }}'::varchar(64)                       as tenant_id,
    '{{ var("source_system") }}'::varchar(32)              as source_system,
    ln.id                                                  as source_loan_deduction_id,
    ln.payroll_run_id,
    {{ payroll_run_group_id('ln.payroll_run_id') }}          as source_payroll_group_id,
    ln.employee_id                                         as source_emp_id,
    ln.loan_id,
    ln.installment_id,
    ln.installment_no,
    'loan'::varchar(16)                                    as deduction_type,
    ln.deduction_name,
    ln.amount,
    ln.remaining_balance,
    ln.is_final_installment,
    ln.proc_year                                           as processing_year,
    ln.proc_month                                          as processing_month,
    coalesce(ln.proc_half, 0)                              as processing_half,
    ln.proc_year,
    ln.proc_month,
    {{ payroll_period_label('ln.proc_year', 'ln.proc_month') }} as period_label,
    coalesce(ln.updated_at, ln.created_at, now())          as _source_updated_at
from {{ source('payroll_processed', 'processed_loan_data') }} ln
