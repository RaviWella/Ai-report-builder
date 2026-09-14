-- Employee no-pay deduction detail by payroll month (mart + silver).
-- Amount: fct_processed_add_ded (deduction lines named No Pay / pay cut).
-- Dates/days: stg_processed_sal_attendance (processed_sal_attendance lines).
-- prl_nopay_data is not staged; nopay_dates/days come from attendance impact lines when present.


with nopay_amount_summary as (
    select
        p.payroll_year                                          as proc_year,
        p.payroll_month                                         as proc_month,
        a.source_emp_id,
        sum(coalesce(a.amount, 0))                              as no_pay_amount
    from {mart_schema}.fct_processed_add_ded a
    inner join {mart_schema}.dim_payroll_period p
        on  p.payroll_period_sk = a.payroll_period_sk
       and p.tenant_id = a.tenant_id
    where a.tenant_id = '{tenant_id}'
      and a.payroll_item_code in ('2', '4')
      and (
            lower(trim(coalesce(a.payroll_item_name, ''))) like '%no%pay%'
         or lower(trim(coalesce(a.payroll_item_name, ''))) like '%paycut%'
         or lower(trim(coalesce(a.payroll_item_name, ''))) like '%pay cut%'
      )
      and coalesce(a.amount, 0) > 0
    group by p.payroll_year, p.payroll_month, a.source_emp_id
),

nopay_dates_agg as (
    select
        sa.processing_year                                      as proc_year,
        sa.processing_month                                     as proc_month,
        sa.source_emp_id,
        string_agg(
            distinct nullif(trim(sa.value_text), ''),
            ', '
            order by nullif(trim(sa.value_text), '')
        )                                                       as nopay_dates,
        sum(
            case
                when lower(trim(coalesce(sa.line_type_name, sa.line_type, ''))) like '%no%pay%'
                  or lower(trim(coalesce(sa.line_type_name, sa.line_type, ''))) like '%nopay%'
                  or lower(trim(coalesce(sa.line_type_name, sa.line_type, ''))) like '%paycut%'
                  or lower(trim(coalesce(sa.line_type_name, sa.line_type, ''))) like '%pay cut%'
                then coalesce(sa.amount, 0)
                else 0
            end
        )                                                       as nopay_days
    from {raw_schema}.stg_processed_sal_attendance sa
    where sa.tenant_id = '{tenant_id}'
      and (
            lower(trim(coalesce(sa.line_type_name, sa.line_type, ''))) like '%no%pay%'
         or lower(trim(coalesce(sa.line_type_name, sa.line_type, ''))) like '%nopay%'
         or lower(trim(coalesce(sa.line_type_name, sa.line_type, ''))) like '%paycut%'
         or lower(trim(coalesce(sa.line_type_name, sa.line_type, ''))) like '%pay cut%'
      )
      and coalesce(sa.amount, 0) > 0
    group by sa.processing_year, sa.processing_month, sa.source_emp_id
),

emp_current as (
    select distinct on (tenant_id, source_emp_id)
        tenant_id,
        source_emp_id,
        emp_no,
        coalesce(nullif(trim(emp_fullname), ''), nullif(trim(emp_name), '')) as employee_name,
        designation_name                                                    as designation
    from {mart_schema}.dim_employee
    where tenant_id = '{tenant_id}'
      and is_current = true
    order by tenant_id, source_emp_id, valid_from desc
)

select
    '{tenant_id}'::varchar(64)                       as tenant_id,
    a.proc_year,
    a.proc_month,
    e.emp_no                                                    as employee_number,
    e.employee_name,
    e.designation,
    d.nopay_dates,
    coalesce(d.nopay_days, 0)::numeric(14, 2)                    as nopay_days,
    a.no_pay_amount
from nopay_amount_summary a
left join nopay_dates_agg d
    on  d.source_emp_id = a.source_emp_id
   and d.proc_year = a.proc_year
   and d.proc_month = a.proc_month
left join emp_current e
    on  e.source_emp_id = a.source_emp_id
   and e.tenant_id = '{tenant_id}'