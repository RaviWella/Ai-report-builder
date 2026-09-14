-- Employee payslip vertical layout (earnings, deductions, employer, bank lines).
-- Source equivalent: processed_sal_basic_data + add_ded + attendance + bank payment data.


with emp as (
    select
        employee_sk,
        source_emp_id,
        emp_no,
        emp_finit,
        emp_fullname,
        designation_name
    from {mart_schema}.dim_employee
    where tenant_id = '{tenant_id}'
      and is_current = true
),

payroll as (
    select
        m.tenant_id,
        m.employee_sk,
        m.payroll_year                                            as proc_year,
        m.payroll_month                                           as proc_month,
        m.basic_salary,
        m.total_additions,
        m.total_deductions,
        m.net_salary,
        m.epf_employee_amount,
        m.tax_amount,
        m.epf_employer_amount,
        m.etf_amount
    from {mart_schema}.mart_processed_payroll_summary m
    where m.tenant_id = '{tenant_id}'
      and coalesce(m.process_status, 'processed') = 'processed'
),

basic_salary as (
    select
        p.proc_year,
        p.proc_month,
        e.emp_no,
        e.emp_finit                                               as emp_name,
        e.emp_fullname                                            as emp_full_name,
        e.designation_name,
        'Earnings'::varchar(32)                                   as section,
        'Basic Salary'::varchar(128)                              as item_name,
        cast(null as varchar(64))                                 as unit,
        p.basic_salary                                            as amount,
        1                                                         as sort_order
    from payroll p
    inner join emp e on e.employee_sk = p.employee_sk
    where coalesce(p.basic_salary, 0) <> 0
),

addition_lines as (
    select
        per.payroll_year                                          as proc_year,
        per.payroll_month                                         as proc_month,
        e.emp_no,
        e.emp_finit                                               as emp_name,
        e.emp_fullname                                            as emp_full_name,
        e.designation_name,
        'Earnings'::varchar(32)                                   as section,
        a.payroll_item_name                                       as item_name,
        cast(a.quantity as varchar(64))                           as unit,
        a.amount,
        2                                                         as sort_order
    from {mart_schema}.fct_processed_add_ded a
    inner join {mart_schema}.dim_payroll_period per
        on  per.payroll_period_sk = a.payroll_period_sk
       and per.tenant_id = a.tenant_id
    inner join emp e on e.employee_sk = a.employee_sk
    where a.tenant_id = '{tenant_id}'
      and a.payroll_item_code in ('1', '3')
      and coalesce(a.amount, 0) <> 0
),

attendance_earnings as (
    select
        sa.processing_year                                        as proc_year,
        sa.processing_month                                         as proc_month,
        e.emp_no,
        e.emp_finit                                               as emp_name,
        e.emp_fullname                                            as emp_full_name,
        e.designation_name,
        'Earnings'::varchar(32)                                   as section,
        coalesce(sa.line_type_name, sa.line_type)                 as item_name,
        sa.value_text                                             as unit,
        sa.amount,
        3                                                         as sort_order
    from {raw_schema}.stg_processed_sal_attendance sa
    inner join emp e on e.source_emp_id = sa.source_emp_id
    where sa.tenant_id = '{tenant_id}'
      and coalesce(sa.amount, 0) <> 0
),

total_earnings as (
    select
        p.proc_year,
        p.proc_month,
        e.emp_no,
        e.emp_finit                                               as emp_name,
        e.emp_fullname                                            as emp_full_name,
        e.designation_name,
        'Earnings'::varchar(32)                                   as section,
        'Total Earnings'::varchar(128)                            as item_name,
        cast(null as varchar(64))                                 as unit,
        coalesce(p.total_additions, 0)                            as amount,
        4                                                         as sort_order
    from payroll p
    inner join emp e on e.employee_sk = p.employee_sk
),

deduction_lines as (
    select
        per.payroll_year                                          as proc_year,
        per.payroll_month                                         as proc_month,
        e.emp_no,
        e.emp_finit                                               as emp_name,
        e.emp_fullname                                            as emp_full_name,
        e.designation_name,
        'Deductions'::varchar(32)                                 as section,
        a.payroll_item_name                                       as item_name,
        cast(null as varchar(64))                                 as unit,
        a.amount,
        5                                                         as sort_order
    from {mart_schema}.fct_processed_add_ded a
    inner join {mart_schema}.dim_payroll_period per
        on  per.payroll_period_sk = a.payroll_period_sk
       and per.tenant_id = a.tenant_id
    inner join emp e on e.employee_sk = a.employee_sk
    where a.tenant_id = '{tenant_id}'
      and a.payroll_item_code in ('2', '4')
      and coalesce(a.amount, 0) <> 0
),

statutory_deductions as (
    select
        p.proc_year,
        p.proc_month,
        e.emp_no,
        e.emp_finit                                               as emp_name,
        e.emp_fullname                                            as emp_full_name,
        e.designation_name,
        'Deductions'::varchar(32)                                 as section,
        v.item_name,
        cast(null as varchar(64))                                 as unit,
        v.amount,
        5                                                         as sort_order
    from payroll p
    inner join emp e on e.employee_sk = p.employee_sk
    cross join lateral (
        values
            ('EPF 8%', p.epf_employee_amount),
            ('APIT', p.tax_amount)
    ) as v(item_name, amount)
    where coalesce(v.amount, 0) > 0

    union all

    select
        per.payroll_year,
        per.payroll_month,
        e.emp_no,
        e.emp_finit,
        e.emp_fullname,
        e.designation_name,
        'Deductions',
        'STAMP DUTY',
        cast(null as varchar(64)),
        a.amount,
        5
    from {mart_schema}.fct_processed_add_ded a
    inner join {mart_schema}.dim_payroll_period per
        on  per.payroll_period_sk = a.payroll_period_sk
       and per.tenant_id = a.tenant_id
    inner join emp e on e.employee_sk = a.employee_sk
    where a.tenant_id = '{tenant_id}'
      and coalesce(a.amount, 0) > 0
      and lower(coalesce(a.payroll_item_name, '')) like '%stamp%'
),

total_deductions as (
    select
        p.proc_year,
        p.proc_month,
        e.emp_no,
        e.emp_finit                                               as emp_name,
        e.emp_fullname                                            as emp_full_name,
        e.designation_name,
        'Deductions'::varchar(32)                                 as section,
        'Total Deductions'::varchar(128)                          as item_name,
        cast(null as varchar(64))                                 as unit,
        p.total_deductions                                        as amount,
        6                                                         as sort_order
    from payroll p
    inner join emp e on e.employee_sk = p.employee_sk
),

net_pay as (
    select
        p.proc_year,
        p.proc_month,
        e.emp_no,
        e.emp_finit                                               as emp_name,
        e.emp_fullname                                            as emp_full_name,
        e.designation_name,
        'Net Pay'::varchar(32)                                    as section,
        'Net Pay'::varchar(128)                                   as item_name,
        cast(null as varchar(64))                                 as unit,
        p.net_salary                                              as amount,
        7                                                         as sort_order
    from payroll p
    inner join emp e on e.employee_sk = p.employee_sk
),

employer_contributions as (
    select
        p.proc_year,
        p.proc_month,
        e.emp_no,
        e.emp_finit                                               as emp_name,
        e.emp_fullname                                            as emp_full_name,
        e.designation_name,
        'Employer Contribution'::varchar(32)                      as section,
        v.item_name,
        cast(null as varchar(64))                                 as unit,
        v.amount,
        8                                                         as sort_order
    from payroll p
    inner join emp e on e.employee_sk = p.employee_sk
    cross join lateral (
        values
            ('EPF', p.epf_employer_amount),
            ('ETF 3%', p.etf_amount)
    ) as v(item_name, amount)
    where coalesce(v.amount, 0) <> 0
),

bank_details as (
    select
        per.payroll_year                                          as proc_year,
        per.payroll_month                                         as proc_month,
        e.emp_no,
        e.emp_finit                                               as emp_name,
        e.emp_fullname                                            as emp_full_name,
        e.designation_name,
        'Bank Details'::varchar(32)                               as section,
        concat(
            coalesce(b.bank_name, 'Bank'),
            ' - ',
            coalesce(br.branch_name, 'Branch'),
            ' - ',
            bi.bank_acc_no
        )                                                         as item_name,
        bi.bank_passbook_name                                     as unit,
        bi.bank_amount                                            as amount,
        9                                                         as sort_order
    from {mart_schema}.fct_salary_bank_instruction bi
    inner join {mart_schema}.dim_payroll_period per
        on  per.payroll_period_sk = bi.payroll_period_sk
       and per.tenant_id = bi.tenant_id
    inner join emp e on e.employee_sk = bi.employee_sk
    left join {mart_schema}.dim_bank b
        on  b.bank_sk = bi.bank_sk
       and b.tenant_id = bi.tenant_id
    left join {mart_schema}.dim_bank_branch br
        on  br.bank_branch_sk = bi.bank_branch_sk
       and br.tenant_id = bi.tenant_id
    where bi.tenant_id = '{tenant_id}'
      and coalesce(bi.is_bank, false) = true
      and nullif(trim(bi.bank_acc_no), '') is not null
      and coalesce(bi.bank_amount, 0) <> 0
)

select
    '{tenant_id}'::varchar(64)                         as tenant_id,
    proc_year,
    proc_month,
    emp_no,
    emp_name,
    emp_full_name,
    designation_name,
    section,
    item_name,
    unit,
    amount,
    sort_order
from basic_salary

union all
select '{tenant_id}', proc_year, proc_month, emp_no, emp_name, emp_full_name,
       designation_name, section, item_name, unit, amount, sort_order
from addition_lines

union all
select '{tenant_id}', proc_year, proc_month, emp_no, emp_name, emp_full_name,
       designation_name, section, item_name, unit, amount, sort_order
from attendance_earnings

union all
select '{tenant_id}', proc_year, proc_month, emp_no, emp_name, emp_full_name,
       designation_name, section, item_name, unit, amount, sort_order
from total_earnings

union all
select '{tenant_id}', proc_year, proc_month, emp_no, emp_name, emp_full_name,
       designation_name, section, item_name, unit, amount, sort_order
from deduction_lines

union all
select '{tenant_id}', proc_year, proc_month, emp_no, emp_name, emp_full_name,
       designation_name, section, item_name, unit, amount, sort_order
from statutory_deductions

union all
select '{tenant_id}', proc_year, proc_month, emp_no, emp_name, emp_full_name,
       designation_name, section, item_name, unit, amount, sort_order
from total_deductions

union all
select '{tenant_id}', proc_year, proc_month, emp_no, emp_name, emp_full_name,
       designation_name, section, item_name, unit, amount, sort_order
from net_pay

union all
select '{tenant_id}', proc_year, proc_month, emp_no, emp_name, emp_full_name,
       designation_name, section, item_name, unit, amount, sort_order
from employer_contributions

union all
select '{tenant_id}', proc_year, proc_month, emp_no, emp_name, emp_full_name,
       designation_name, section, item_name, unit, amount, sort_order
from bank_details

order by proc_year desc, proc_month desc, emp_no, sort_order, section, item_name