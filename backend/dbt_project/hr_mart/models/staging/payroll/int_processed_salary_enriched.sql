-- Enriched processed salary snapshot (§7.1 measures from engine staging).

{{ config(materialized='view') }}

select
    b.tenant_id,
    b.source_system,
    b.source_processed_salary_id,
    b.payroll_run_id,
    b.source_payroll_group_id,
    b.source_emp_id,
    b.processing_year,
    b.processing_month,
    b.processing_half,
    b.proc_year,
    b.proc_month,
    b.period_label,
    b.process_status,
    b.basic_salary,
    coalesce(b.allowances, 0)
        + coalesce(b.overtime_pay, 0)
        + coalesce(b.bonuses, 0)                            as total_additions,
    b.gross_salary,
    b.total_deductions,
    b.net_salary,
    b.tax_deduction                                         as tax_amount,
    b.epf_employee_amount,
    b.epf_employer_amount,
    b.etf_amount,
    b.pay_cut_amount,
    b.increment_amount,
    b.ot_amount,
    b.bonus_amount,
    b.attendance_deduction,
    b.nopay_deduction,
    b.loan_deduction,
    b.installment_deduction,
    b.service_charge,
    b.currency_code,
    b.exchange_rate,
    b.is_multi_currency,
    b.is_compliance_processed,
    b.original_process_reference,
    b.reversal_timestamp,
    b.reversed_by,
    b.reversal_reason,
    make_date(b.processing_year::integer, b.processing_month::integer, 1)
                                                            as processed_month,
    (
        make_date(b.processing_year::integer, b.processing_month::integer, 1)
        + interval '1 month - 1 day'
    )::timestamptz                                          as process_timestamp,
    b._source_updated_at
from {{ ref('stg_processed_sal_basic_data') }} b
