-- Wide paysheet: core salary columns + one column per distinct fixed/variable add/ded item.

{{ config(materialized='table', tags=['warehouse', 'warehouse_payroll', 'warehouse_marts']) }}

with vertical as (
    select
        tenant_id,
        employee_sk,
        payroll_period_sk,
        pivot_key,
        amount
    from {{ ref('int_payroll_paysheet_vertical') }}
),

pivoted as (
    select
        tenant_id,
        employee_sk,
        payroll_period_sk,
        {{ payroll_pivot_sum_columns() }}
    from vertical
    group by tenant_id, employee_sk, payroll_period_sk
),

core as (
    select
        tenant_id,
        employee_sk,
        payroll_period_sk,
        emp_no,
        emp_fullname,
        designation,
        branch,
        payroll_group_name,
        payroll_year,
        payroll_month,
        payroll_half,
        basic_salary,
        gross_salary,
        net_salary,
        total_allowance,
        total_deduction,
        ot_amount,
        bonus_amount,
        tax_amount,
        epf_employee,
        epf_employer,
        etf_amount,
        nopay_amount,
        loan_deduction,
        pay_cut_amount,
        increment_amount,
        payroll_currency,
        process_status
    from {{ ref('mart_horizontal_paysheet_core') }}
)

select
    c.*,
    {{ payroll_pivot_coalesce_columns('p') }},
    current_timestamp                                       as _refreshed_at
from core c
left join pivoted p
    on  p.tenant_id = c.tenant_id
   and p.employee_sk = c.employee_sk
   and p.payroll_period_sk = c.payroll_period_sk
