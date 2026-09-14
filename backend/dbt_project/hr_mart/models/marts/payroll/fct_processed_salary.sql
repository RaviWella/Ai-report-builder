-- Processed payroll snapshot fact.
-- Grain: employee_sk × payroll_period_sk × payroll_group_sk

{{ config(
    materialized='incremental',
    unique_key=['tenant_id', 'source_system', 'source_processed_salary_id'],
    incremental_strategy='delete+insert',
    on_schema_change='sync_all_columns',
    tags=['warehouse', 'warehouse_payroll', 'warehouse_marts'],
    indexes=[
        {
            'columns': [
                'tenant_id', 'employee_sk', 'payroll_period_sk', 'payroll_group_sk'
            ],
            'unique': true
        }
    ]
) }}

with basic as (
    select * from {{ ref('int_processed_salary_enriched') }}
    {% if is_incremental() %}
    where _source_updated_at >= (
        select coalesce(max(_source_updated_at), '1970-01-01'::timestamptz) - interval '1 hour'
        from {{ this }}
    )
    {% endif %}
),

emp_current as (
    select employee_sk, tenant_id, source_system, source_emp_id
    from {{ ref('dim_employee') }}
    where is_current = true
),

periods as (
    select payroll_period_sk, tenant_id, payroll_year, payroll_month, payroll_half
    from {{ ref('dim_payroll_period') }}
),

groups as (
    select payroll_group_sk, tenant_id, source_system, source_payroll_group_id
    from {{ ref('dim_payroll_group') }}
),

joined as (
    select
        b.tenant_id,
        b.source_system,
        b.source_processed_salary_id,
        b.payroll_run_id,
        emp.employee_sk,
        p.payroll_period_sk,
        g.payroll_group_sk,
        b.source_emp_id,
        b.source_payroll_group_id,
        b.period_label,
        b.processing_year                                         as process_year,
        b.processing_month                                        as process_month,
        b.processing_half                                         as process_half,
        b.processed_month,
        b.process_status,
        b.basic_salary,
        b.total_additions,
        b.gross_salary,
        b.total_deductions,
        b.net_salary,
        b.tax_amount,
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
        b.process_timestamp,
        b._source_updated_at
    from basic b
    inner join emp_current emp
        on emp.tenant_id = b.tenant_id
       and emp.source_emp_id = b.source_emp_id
    inner join periods p
        on p.tenant_id = b.tenant_id
       and p.payroll_year = b.processing_year
       and p.payroll_month = b.processing_month
       and p.payroll_half = coalesce(b.processing_half, 0)
    inner join groups g
        on g.tenant_id = b.tenant_id
       and g.source_payroll_group_id = b.source_payroll_group_id
)

select
    {{ dbt_utils.generate_surrogate_key([
        'tenant_id', 'source_system', 'source_processed_salary_id'
    ]) }}                                                 as processed_salary_sk,
    j.*,
    current_timestamp                                     as _loaded_at
from joined j
