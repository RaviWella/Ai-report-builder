-- Horizontal paysheet core — employee × period snapshot from processed salary fact.

{{ config(materialized='table', tags=['warehouse', 'warehouse_payroll', 'warehouse_marts']) }}

with salary as (
    select * from {{ ref('fct_processed_salary') }}
),

emp as (
    select employee_sk, tenant_id, emp_no, emp_fullname, designation_name, branch_id
    from {{ ref('dim_employee') }}
    where is_current = true
),

pg as (
    select payroll_group_sk, payroll_group_name from {{ ref('dim_payroll_group') }}
),

period as (
    select * from {{ ref('dim_payroll_period') }}
)

select
    s.tenant_id,
    s.employee_sk,
    s.payroll_period_sk,
    e.emp_no,
    e.emp_fullname,
    e.designation_name                                      as designation,
    e.branch_id                                             as branch,
    pg.payroll_group_name,
    p.payroll_year,
    p.payroll_month,
    p.payroll_half,
    s.basic_salary,
    s.gross_salary,
    s.net_salary,
    s.total_additions                                       as total_allowance,
    s.total_deductions                                      as total_deduction,
    s.ot_amount,
    s.bonus_amount,
    s.tax_amount,
    s.epf_employee_amount                                   as epf_employee,
    s.epf_employer_amount                                   as epf_employer,
    s.etf_amount,
    s.nopay_deduction                                       as nopay_amount,
    s.loan_deduction + s.installment_deduction              as loan_deduction,
    s.pay_cut_amount,
    s.increment_amount,
    s.currency_code                                         as payroll_currency,
    s.process_status,
    current_timestamp                                       as _refreshed_at
from salary s
left join emp e
    on  e.employee_sk = s.employee_sk
   and e.tenant_id = s.tenant_id
left join pg
    on  pg.payroll_group_sk = s.payroll_group_sk
left join period p
    on  p.payroll_period_sk = s.payroll_period_sk
