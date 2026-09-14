-- Employee-level allowance pivot, OT, org attributes, and payroll totals (mart / gold).
-- Source equivalent: processed_sal_add_ded + prl_overtime + hr_empbasic + company_structure + processed_sal_basic_data.
-- OT uses mart_processed_payroll_summary.ot_amount (not prl_overtime formula).


with emp_current as (
    select
        e.tenant_id,
        e.employee_sk,
        e.source_emp_id,
        e.emp_no,
        coalesce(nullif(trim(e.emp_fullname), ''), nullif(trim(e.emp_name), ''))
                                                                as emp_name,
        e.gender,
        e.employee_category                                     as category_name,
        ou.org_unit_name                                        as hierarchy_name,
        coalesce(nullif(trim(e.employee_category), ''), 'Unassigned') as je
    from {mart_schema}.dim_employee e
    left join {mart_schema}.dim_org_unit ou
        on  ou.org_unit_sk = e.org_unit_sk
       and ou.tenant_id = e.tenant_id
    where e.tenant_id = '{tenant_id}'
      and e.is_current = true
),

allowance_pivot as (
    select
        p.payroll_year                                          as proc_year,
        p.payroll_month                                         as proc_month,
        a.source_emp_id,
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
    where a.tenant_id = '{tenant_id}'
      and a.payroll_item_code in ('1', '3')
      and lower(coalesce(a.payroll_item_name, '')) not like '%arrear%'
      and lower(coalesce(a.payroll_item_name, '')) not like '%recovery%'
    group by p.payroll_year, p.payroll_month, a.source_emp_id
),

ot_pivot as (
    select
        m.payroll_year                                          as proc_year,
        m.payroll_month                                         as proc_month,
        e.source_emp_id,
        sum(coalesce(m.ot_amount, 0))                           as ot_amount
    from {mart_schema}.mart_processed_payroll_summary m
    inner join emp_current e
        on  e.employee_sk = m.employee_sk
       and e.tenant_id = m.tenant_id
    where m.tenant_id = '{tenant_id}'
      and coalesce(m.process_status, 'processed') = 'processed'
    group by m.payroll_year, m.payroll_month, e.source_emp_id
),

combined as (
    select
        coalesce(a.proc_year, o.proc_year)                      as proc_year,
        coalesce(a.proc_month, o.proc_month)                    as proc_month,
        coalesce(a.source_emp_id, o.source_emp_id)              as source_emp_id,
        coalesce(a.fuel_transport_allowance, 0)                 as fuel_transport_allowance,
        coalesce(a.inflation_allowance, 0)                      as inflation_allowance,
        coalesce(a.blend_allowance, 0)                          as blend_allowance,
        coalesce(a.dollar_pegged, 0)                            as dollar_pegged,
        coalesce(a.sales_incentive, 0)                          as sales_incentive,
        coalesce(o.ot_amount, 0)                                as ot_amount
    from allowance_pivot a
    full outer join ot_pivot o
        on  a.proc_year = o.proc_year
       and a.proc_month = o.proc_month
       and a.source_emp_id = o.source_emp_id
)

select
    '{tenant_id}'::varchar(64)                       as tenant_id,
    c.proc_year,
    c.proc_month,
    e.emp_no,
    e.emp_name,
    e.gender,
    e.hierarchy_name,
    e.category_name,
    e.je,
    c.fuel_transport_allowance,
    c.inflation_allowance,
    c.blend_allowance,
    c.dollar_pegged,
    c.sales_incentive,
    c.ot_amount,
    c.fuel_transport_allowance
        + c.inflation_allowance
        + c.blend_allowance
        + c.dollar_pegged
        + c.sales_incentive                                     as total_allowances,
    c.fuel_transport_allowance
        + c.inflation_allowance
        + c.blend_allowance
        + c.dollar_pegged
        + c.sales_incentive
        + c.ot_amount                                           as gross_10th_payment,
    c.fuel_transport_allowance
        + c.inflation_allowance
        + c.blend_allowance
        + c.dollar_pegged
        + c.sales_incentive
        + c.ot_amount                                           as total_cost,
    coalesce(p.total_deductions, 0)                             as deductions,
    coalesce(p.net_salary, 0)                                   as net_pay
from combined c
left join emp_current e
    on  e.source_emp_id = c.source_emp_id
   and e.tenant_id = '{tenant_id}'
left join {mart_schema}.mart_processed_payroll_summary p
    on  p.employee_sk = e.employee_sk
   and p.tenant_id = e.tenant_id
   and p.payroll_year = c.proc_year
   and p.payroll_month = c.proc_month
   and coalesce(p.process_status, 'processed') = 'processed'
where c.proc_year is not null
  and c.proc_month is not null