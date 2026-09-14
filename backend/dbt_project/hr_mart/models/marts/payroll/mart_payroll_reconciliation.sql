-- Payroll finance reconciliation mart (§8.2).

{{ config(materialized='table', tags=['warehouse', 'warehouse_payroll', 'warehouse_marts']) }}

with salary as (
    select
        tenant_id,
        payroll_group_sk,
        payroll_period_sk,
        sum(gross_salary)                                     as gross_salary_total,
        sum(net_salary)                                       as net_salary_total,
        sum(total_additions)                                  as total_additions,
        sum(total_deductions)                                 as total_deductions,
        sum(epf_employee_amount)                              as epf_employee_total,
        sum(epf_employer_amount)                              as epf_employer_total,
        sum(etf_amount)                                       as etf_total,
        sum(tax_amount)                                       as tax_total,
        sum(loan_deduction)                                   as loan_deduction_total,
        sum(installment_deduction)                            as installment_deduction_total,
        sum(attendance_deduction)                             as attendance_deduction_total,
        count(distinct employee_sk)                           as employee_count
    from {{ ref('fct_processed_salary') }}
    group by tenant_id, payroll_group_sk, payroll_period_sk
),

periods as (
    select * from {{ ref('dim_payroll_period') }}
),

groups as (
    select * from {{ ref('dim_payroll_group') }}
)

select
    s.tenant_id,
    s.payroll_group_sk,
    s.payroll_period_sk,
    g.payroll_group_name,
    p.payroll_year,
    p.payroll_month,
    p.payroll_half,
    s.gross_salary_total,
    s.net_salary_total,
    s.total_additions,
    s.total_deductions,
    s.epf_employee_total,
    s.epf_employer_total,
    s.etf_total,
    s.tax_total,
    s.loan_deduction_total + s.installment_deduction_total as loan_deduction_totals,
    s.attendance_deduction_total,
    s.employee_count,
    abs(
        coalesce(s.gross_salary_total, 0)
        - coalesce(s.total_additions, 0)
        - coalesce(s.total_deductions, 0)
        - coalesce(s.net_salary_total, 0)
    )                                                       as payroll_variance,
    case
        when abs(
            coalesce(s.gross_salary_total, 0)
            - coalesce(s.total_additions, 0)
            - coalesce(s.total_deductions, 0)
            - coalesce(s.net_salary_total, 0)
        ) < 0.01 then 'reconciled'
        else 'variance'
    end                                                     as reconciliation_status,
    current_timestamp                                       as _refreshed_at
from salary s
left join groups g on g.payroll_group_sk = s.payroll_group_sk
left join periods p on p.payroll_period_sk = s.payroll_period_sk
