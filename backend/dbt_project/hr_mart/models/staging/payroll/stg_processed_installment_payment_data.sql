{{ config(materialized='view') }}

select
    '{{ target.name }}'::varchar(64)                       as tenant_id,
    '{{ var("source_system") }}'::varchar(32)              as source_system,
    ip.id                                                  as source_loan_deduction_id,
    ip.payroll_run_id,
    {{ payroll_run_group_id('ip.payroll_run_id') }}          as source_payroll_group_id,
    ip.employee_id                                         as source_emp_id,
    ip.loan_id,
    ip.installment_id,
    ip.installment_no,
    'installment'::varchar(16)                             as deduction_type,
    ip.deduction_name,
    ip.amount,
    ip.remaining_balance,
    ip.is_final_installment,
    ip.proc_year                                           as processing_year,
    ip.proc_month                                          as processing_month,
    coalesce(ip.proc_half, 0)                              as processing_half,
    ip.proc_year,
    ip.proc_month,
    {{ payroll_period_label('ip.proc_year', 'ip.proc_month') }} as period_label,
    coalesce(ip.updated_at, ip.created_at, now())          as _source_updated_at
from {{ source('payroll_processed', 'processed_installment_payment_data') }} ip
