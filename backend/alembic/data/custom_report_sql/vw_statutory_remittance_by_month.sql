-- Statutory / welfare remittance summary by payroll month (mart layer).
-- Mirrors legacy MintHRM report shape: payment_type × year × month.
-- Schema: custom_reports


with salary as (
    select *
    from {mart_schema}.mart_processed_payroll_summary
    where tenant_id = '{tenant_id}'
      and coalesce(process_status, 'processed') = 'processed'
),

welfare as (
    select
        a.tenant_id,
        p.payroll_year,
        p.payroll_month,
        a.source_emp_id,
        a.amount
    from {mart_schema}.fct_processed_add_ded a
    inner join {mart_schema}.dim_payroll_period p
        on p.payroll_period_sk = a.payroll_period_sk
       and p.tenant_id = a.tenant_id
    where a.tenant_id = '{tenant_id}'
      and a.payroll_item_code in ('2', '4')
      and coalesce(a.amount, 0) > 0
      and (
            lower(coalesce(a.payroll_item_name, '')) like '%welfare%'
         or lower(coalesce(a.payroll_item_name, '')) like '%donation%'
         or lower(coalesce(a.payroll_item_name, '')) like '%society%'
         or lower(coalesce(a.payroll_item_name, '')) like '%soci%'
         or lower(coalesce(a.payroll_item_name, '')) like '%fund%'
      )
),

stamp_duty as (
    select
        a.tenant_id,
        p.payroll_year,
        p.payroll_month,
        a.source_emp_id,
        a.amount
    from {mart_schema}.fct_processed_add_ded a
    inner join {mart_schema}.dim_payroll_period p
        on p.payroll_period_sk = a.payroll_period_sk
       and p.tenant_id = a.tenant_id
    where a.tenant_id = '{tenant_id}'
      and coalesce(a.amount, 0) > 0
      and lower(coalesce(a.payroll_item_name, '')) like '%stamp%'
),

lump_sum_tax as (
    select
        t.tenant_id,
        p.payroll_year,
        p.payroll_month,
        t.employee_sk,
        t.tax_amount
    from {mart_schema}.fct_processed_tax t
    inner join {mart_schema}.dim_payroll_period p
        on p.payroll_period_sk = t.payroll_period_sk
       and p.tenant_id = t.tenant_id
    where t.tenant_id = '{tenant_id}'
      and coalesce(t.tax_amount, 0) > 0
      and (
            lower(coalesce(t.tax_type, '')) like '%lump%'
         or lower(coalesce(t.tax_type, '')) like '%dynamic%'
         or lower(coalesce(t.tax_type, '')) like '%bonus%tax%'
      )
)

select
    m.tenant_id,
    m.payroll_year                                            as reporting_year,
    m.payroll_month                                           as reporting_month,
    'APIT'::varchar(32)                                       as payment_type,
    'Account Pay'::varchar(32)                                as cheque_type,
    'The Commissioner General of Inland Revenue'::varchar(128)
                                                              as cheque_in_favour_of,
    count(*) filter (where coalesce(m.tax_amount, 0) > 0)     as headcount,
    0::numeric(18, 2)                                         as employee_contribution,
    0::numeric(18, 2)                                         as employer_contribution,
    sum(coalesce(m.tax_amount, 0))                            as total_payable_amount
from salary m
group by m.tenant_id, m.payroll_year, m.payroll_month

union all

select
    m.tenant_id,
    m.payroll_year,
    m.payroll_month,
    'EPF 20%',
    'Online Transfer',
    'Employee Provident Fund',
    count(*) filter (
        where coalesce(m.epf_employee_amount, 0) > 0
           or coalesce(m.epf_employer_amount, 0) > 0
    ),
    sum(coalesce(m.epf_employee_amount, 0)),
    sum(coalesce(m.epf_employer_amount, 0)),
    sum(coalesce(m.epf_employee_amount, 0)) + sum(coalesce(m.epf_employer_amount, 0))
from salary m
group by m.tenant_id, m.payroll_year, m.payroll_month

union all

select
    m.tenant_id,
    m.payroll_year,
    m.payroll_month,
    'ETF 3%',
    'Online Transfer',
    'Employee Provident Fund',
    count(*) filter (where coalesce(m.etf_amount, 0) > 0),
    0::numeric(18, 2),
    sum(coalesce(m.etf_amount, 0)),
    sum(coalesce(m.etf_amount, 0))
from salary m
group by m.tenant_id, m.payroll_year, m.payroll_month

union all

select
    s.tenant_id,
    s.payroll_year,
    s.payroll_month,
    'STAMP DUTY',
    'Account Pay',
    'Employee Trust Fund Board',
    count(distinct s.source_emp_id),
    0::numeric(18, 2),
    0::numeric(18, 2),
    sum(coalesce(s.amount, 0))
from stamp_duty s
group by s.tenant_id, s.payroll_year, s.payroll_month

union all

select
    l.tenant_id,
    l.payroll_year,
    l.payroll_month,
    'LUMP SUM TAX',
    'Account Pay',
    'The Commissioner General of Inland Revenue',
    count(distinct l.employee_sk),
    0::numeric(18, 2),
    0::numeric(18, 2),
    sum(coalesce(l.tax_amount, 0))
from lump_sum_tax l
group by l.tenant_id, l.payroll_year, l.payroll_month

union all

select
    w.tenant_id,
    w.payroll_year,
    w.payroll_month,
    'WELFARE CONTRIBUTION',
    'Journal Entry',
    'On A/C/C Amazon Welfare Soci',
    count(distinct w.source_emp_id),
    sum(coalesce(w.amount, 0)),
    0::numeric(18, 2),
    sum(coalesce(w.amount, 0))
from welfare w
group by w.tenant_id, w.payroll_year, w.payroll_month