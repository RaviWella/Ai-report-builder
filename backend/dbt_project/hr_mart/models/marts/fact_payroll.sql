-- fact_payroll — backward-compatible view over Phase 6 payroll mart.

{{ config(materialized='view') }}

select
    s.source_processed_salary_id                           as id,
    s.payroll_run_id,
    m.employee_sk,
    e.source_emp_id                                        as employee_id,
    e.emp_section_id                                       as department_id,
    e.branch_id,
    m.payroll_year,
    m.payroll_month,
    to_char(m.period_start_date, 'YYYY-MM')                as period_label,
    m.process_status                                       as run_status,
    m.basic_salary,
    m.total_additions                                      as allowances,
    cast(null as numeric(14, 2))                           as overtime_pay,
    cast(null as numeric(14, 2))                           as bonuses,
    m.gross_salary,
    m.tax_amount                                           as tax_deduction,
    greatest(m.total_deductions - coalesce(m.tax_amount, 0), 0)
                                                           as other_deductions,
    m.total_deductions,
    m.net_salary
from {{ ref('mart_processed_payroll_summary') }} m
left join lateral (
    select
        s.source_processed_salary_id,
        s.payroll_run_id
    from {{ ref('fct_processed_salary') }} s
    where s.tenant_id = m.tenant_id
      and s.employee_sk = m.employee_sk
      and s.payroll_period_sk = m.payroll_period_sk
    order by s.net_salary desc nulls last, s.source_processed_salary_id desc
    limit 1
) s on true
left join {{ ref('dim_employee') }} e
    on  e.employee_sk = m.employee_sk
   and e.is_current = true
