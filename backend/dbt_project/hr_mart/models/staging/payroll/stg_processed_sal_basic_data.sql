-- Finalized payroll snapshot staging (engine output, not recalculated).

{{ config(materialized='view') }}

with details as (
    select * from {{ source('payroll_processed', 'processed_sal_basic_data') }}
),

runs as (
    select * from {{ source('hr_raw', 'stg_payroll_runs') }}
)

select
    '{{ target.name }}'::varchar(64)                       as tenant_id,
    '{{ var("source_system") }}'::varchar(32)              as source_system,
    d.id                                                   as source_processed_salary_id,
    d.payroll_run_id,
    {{ payroll_run_group_id('d.payroll_run_id') }}           as source_payroll_group_id,
    d.employee_id                                          as source_emp_id,

    r.payroll_year                                         as processing_year,
    r.payroll_month                                        as processing_month,
    coalesce(d.processing_half, r.payroll_half, 0)         as processing_half,
    d.ref_fortnight_id,

    r.payroll_year                                         as proc_year,
    r.payroll_month                                        as proc_month,
    {{ payroll_period_label('r.payroll_year', 'r.payroll_month') }}
                                                           as period_label,

    r.run_code,
    coalesce(d.process_status, r.status, 'processed')      as process_status,
    d.basic_salary,
    d.allowances,
    d.overtime_pay,
    d.bonuses,
    d.gross_salary,
    d.tax_deduction,
    d.other_deductions,
    d.tax_deduction + d.other_deductions                   as total_deductions,
    d.net_salary,
    d.epf_employee_amount,
    d.epf_employer_amount,
    d.etf_amount,
    d.pay_cut_amount,
    d.increment_amount,
    coalesce(d.ot_amount, d.overtime_pay, 0)               as ot_amount,
    coalesce(d.bonus_amount, d.bonuses, 0)                 as bonus_amount,
    coalesce(d.attendance_deduction, 0)                    as attendance_deduction,
    coalesce(d.nopay_deduction, 0)                         as nopay_deduction,
    coalesce(d.loan_deduction, 0)                          as loan_deduction,
    coalesce(d.installment_deduction, 0)                   as installment_deduction,
    coalesce(d.service_charge, 0)                          as service_charge,
    coalesce(d.currency_code, 'LKR')                       as currency_code,
    coalesce(d.exchange_rate, 1)                           as exchange_rate,
    coalesce(d.is_multi_currency, false)                   as is_multi_currency,
    coalesce(d.is_compliance_processed, false)             as is_compliance_processed,
    d.original_process_reference,
    d.reversal_timestamp,
    d.reversed_by,
    d.reversal_reason,
    coalesce(d.updated_at, d.created_at, now())            as _source_updated_at
from details d
inner join runs r on r.id = d.payroll_run_id
