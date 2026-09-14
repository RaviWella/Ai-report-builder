-- JE allowance & OT cost summary by payroll month (mart / gold layer).
-- Source equivalent: processed_sal_add_ded + prl_overtime rolled up by employee category (JE).
-- OT uses mart_processed_payroll_summary.ot_amount (processed payroll OT pay), not prl_overtime formula.


with emp_org as (
    select
        e.tenant_id,
        e.employee_sk,
        e.emp_no,
        coalesce(nullif(trim(e.employee_category), ''), 'Unassigned') as je
    from {mart_schema}.dim_employee e
    where e.tenant_id = '{tenant_id}'
      and e.is_current = true
),

employee_allowances as (
    select
        p.payroll_year                                          as proc_year,
        p.payroll_month                                         as proc_month,
        eo.emp_no,
        eo.je,
        sum(
            case
                when lower(coalesce(a.payroll_item_name, '')) like '%fuel%'
                  or lower(coalesce(a.payroll_item_name, '')) like '%transport%'
                then coalesce(a.amount, 0)
                else 0
            end
        )                                                       as fuel_transport_allowance,
        sum(
            case
                when lower(coalesce(a.payroll_item_name, '')) like '%inflation%'
                then coalesce(a.amount, 0)
                else 0
            end
        )                                                       as inflation_allowance,
        sum(
            case
                when lower(coalesce(a.payroll_item_name, '')) like '%blend%'
                then coalesce(a.amount, 0)
                else 0
            end
        )                                                       as blend_allowance,
        sum(
            case
                when lower(coalesce(a.payroll_item_name, '')) like '%dollar%'
                  or lower(coalesce(a.payroll_item_name, '')) like '%pegged%'
                then coalesce(a.amount, 0)
                else 0
            end
        )                                                       as dollar_pegged,
        sum(
            case
                when lower(coalesce(a.payroll_item_name, '')) like '%sales%'
                  or lower(coalesce(a.payroll_item_name, '')) like '%incentive%'
                then coalesce(a.amount, 0)
                else 0
            end
        )                                                       as sales_incentive
    from {mart_schema}.fct_processed_add_ded a
    inner join {mart_schema}.dim_payroll_period p
        on  p.payroll_period_sk = a.payroll_period_sk
       and p.tenant_id = a.tenant_id
    inner join emp_org eo
        on  eo.employee_sk = a.employee_sk
       and eo.tenant_id = a.tenant_id
    where a.tenant_id = '{tenant_id}'
      and a.payroll_item_code in ('1', '3')
      and lower(coalesce(a.payroll_item_name, '')) not like '%arrear%'
      and lower(coalesce(a.payroll_item_name, '')) not like '%recovery%'
    group by p.payroll_year, p.payroll_month, eo.emp_no, eo.je
),

employee_ot as (
    select
        m.payroll_year                                          as proc_year,
        m.payroll_month                                         as proc_month,
        m.emp_no,
        eo.je,
        sum(coalesce(m.ot_amount, 0))                           as ot_amount
    from {mart_schema}.mart_processed_payroll_summary m
    inner join emp_org eo
        on  eo.employee_sk = m.employee_sk
       and eo.tenant_id = m.tenant_id
    where m.tenant_id = '{tenant_id}'
      and coalesce(m.process_status, 'processed') = 'processed'
    group by m.payroll_year, m.payroll_month, m.emp_no, eo.je
),

combined as (
    select
        coalesce(a.proc_year, o.proc_year)                      as proc_year,
        coalesce(a.proc_month, o.proc_month)                  as proc_month,
        coalesce(a.emp_no, o.emp_no)                            as emp_no,
        coalesce(a.je, o.je)                                    as je,
        coalesce(a.fuel_transport_allowance, 0)               as fuel_transport_allowance,
        coalesce(a.inflation_allowance, 0)                      as inflation_allowance,
        coalesce(a.blend_allowance, 0)                          as blend_allowance,
        coalesce(a.dollar_pegged, 0)                            as dollar_pegged,
        coalesce(a.sales_incentive, 0)                          as sales_incentive,
        coalesce(o.ot_amount, 0)                                as ot_amount
    from employee_allowances a
    full outer join employee_ot o
        on  a.proc_year = o.proc_year
       and a.proc_month = o.proc_month
       and a.emp_no = o.emp_no
)

select
    '{tenant_id}'::varchar(64)                       as tenant_id,
    proc_year,
    proc_month,
    coalesce(je, 'Unassigned')                                  as row_labels,
    count(distinct emp_no)                                      as count_of_emp_no,
    sum(fuel_transport_allowance)                               as sum_of_fuel_transport_allowance,
    sum(inflation_allowance)                                    as sum_of_inflation_allowance,
    sum(blend_allowance)                                        as sum_of_blend_allowance,
    sum(dollar_pegged)                                          as sum_of_dollar_pegged,
    sum(sales_incentive)                                        as sum_of_sales_incentive,
    sum(ot_amount)                                              as sum_of_ot,
    sum(fuel_transport_allowance)
        + sum(inflation_allowance)
        + sum(blend_allowance)
        + sum(dollar_pegged)
        + sum(sales_incentive)
        + sum(ot_amount)                                          as sum_of_total_cost
from combined
where proc_year is not null
  and proc_month is not null
group by proc_year, proc_month, coalesce(je, 'Unassigned')