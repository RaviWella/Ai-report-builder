-- vw_payroll_summary — AI-safe payroll view (§8.1 mart)

{{ config(materialized='view') }}

select
    m.tenant_id,
    m.employee_sk,
    e.source_emp_id                                        as employee_id,
    e.emp_section_id                                       as department_id,
    e.branch_id,
    to_char(m.period_start_date, 'YYYY-MM')               as period_label,
    m.payroll_year,
    m.payroll_month,
    m.payroll_half,
    m.emp_no,
    m.emp_fullname,
    m.designation,
    m.legal_entity,
    m.branch,
    m.payroll_group_name,
    m.basic_salary,
    m.gross_salary,
    m.total_additions,
    m.total_deductions,
    m.net_salary,
    m.tax_amount,
    m.epf_employee_amount,
    m.epf_employer_amount,
    m.etf_amount,
    m.pay_cut_amount,
    m.increment_amount,
    m.process_status                                       as run_status
from {{ ref('mart_processed_payroll_summary') }} m
left join {{ ref('dim_employee') }} e
    on  e.employee_sk = m.employee_sk
   and e.is_current = true
