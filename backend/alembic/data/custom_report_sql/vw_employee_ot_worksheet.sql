-- Employee OT worksheet by payroll month (silver prl_overtime + gold dimensions).
-- Mirrors ot_worksheet / ot_allowance_report from MintHRM prl_overtime.


with emp_current as (
    select
        e.tenant_id,
        e.employee_sk,
        e.source_emp_id,
        e.emp_no,
        coalesce(nullif(trim(e.emp_fullname), ''), nullif(trim(e.emp_name), ''))
                                                                as emp_name,
        e.designation_name,
        e.employee_category                                     as category_name,
        ou.org_unit_name                                        as hierarchy_name,
        coalesce(nullif(trim(e.employee_category), ''), 'Unassigned') as je,
        coalesce(e.basic_salary, 0)                             as employee_basic_salary
    from {mart_schema}.dim_employee e
    left join {mart_schema}.dim_org_unit ou
        on  ou.org_unit_sk = e.org_unit_sk
       and ou.tenant_id = e.tenant_id
    where e.tenant_id = '{tenant_id}'
      and e.is_current = true
),

payroll_context as (
    select
        m.tenant_id,
        m.employee_sk,
        m.payroll_year,
        m.payroll_month,
        coalesce(m.basic_salary, 0)                             as basic_salary,
        m.payroll_group_name
    from {mart_schema}.mart_processed_payroll_summary m
    where m.tenant_id = '{tenant_id}'
      and coalesce(m.process_status, 'processed') = 'processed'
),

ot_lines as (
    select
        o.proc_year,
        o.proc_month,
        o.source_emp_id,
        sum(coalesce(o.ot_inone_hours, 0))                      as ot_inone_hours,
        sum(coalesce(o.ot_outone_hours, 0))                     as ot_outone_hours,
        sum(coalesce(o.ot_dayorhour_hours, 0))                  as ot_dayorhour_hours
    from {raw_schema}.stg_processed_prl_overtime o
    where o.tenant_id = '{tenant_id}'
    group by o.proc_year, o.proc_month, o.source_emp_id
),

grouped as (
    select
        ot.proc_year,
        ot.proc_month,
        e.emp_no,
        e.emp_name,
        e.designation_name,
        e.category_name,
        e.hierarchy_name,
        e.je,
        coalesce(pc.payroll_group_name, 'Unassigned')             as payroll_group_name,
        coalesce(nullif(pc.basic_salary, 0), e.employee_basic_salary, 0)
                                                                as basic_salary,
        round((coalesce(nullif(pc.basic_salary, 0), e.employee_basic_salary, 0) / 200 * 1.5)::numeric, 2)
                                                                as ot_1_5_rate,
        round(sum(ot.ot_inone_hours)::numeric, 2)               as ot_1_5_hours,
        round((sum(ot.ot_inone_hours) * (coalesce(nullif(pc.basic_salary, 0), e.employee_basic_salary, 0) / 200 * 1.5))::numeric, 2)
                                                                as ot_1_5_amount,
        round((coalesce(nullif(pc.basic_salary, 0), e.employee_basic_salary, 0) / 200 * 2)::numeric, 2)
                                                                as ot_2_rate,
        round(sum(ot.ot_outone_hours)::numeric, 2)                as ot_2_hours,
        round((sum(ot.ot_outone_hours) * (coalesce(nullif(pc.basic_salary, 0), e.employee_basic_salary, 0) / 200 * 2))::numeric, 2)
                                                                as ot_2_amount,
        round((coalesce(nullif(pc.basic_salary, 0), e.employee_basic_salary, 0) / 200 * 3)::numeric, 2)
                                                                as ot_3_rate,
        round(sum(ot.ot_dayorhour_hours)::numeric, 2)             as ot_3_hours,
        round((sum(ot.ot_dayorhour_hours) * (coalesce(nullif(pc.basic_salary, 0), e.employee_basic_salary, 0) / 200 * 3))::numeric, 2)
                                                                as ot_3_amount
    from ot_lines ot
    inner join emp_current e
        on  e.source_emp_id = ot.source_emp_id
       and e.tenant_id = '{tenant_id}'
    left join payroll_context pc
        on  pc.employee_sk = e.employee_sk
       and pc.payroll_year = ot.proc_year
       and pc.payroll_month = ot.proc_month
    where coalesce(nullif(pc.basic_salary, 0), e.employee_basic_salary, 0) > 0
    group by
        ot.proc_year,
        ot.proc_month,
        e.emp_no,
        e.emp_name,
        e.designation_name,
        e.category_name,
        e.hierarchy_name,
        e.je,
        pc.payroll_group_name,
        coalesce(nullif(pc.basic_salary, 0), e.employee_basic_salary, 0)
)

select
    '{tenant_id}'::varchar(64)                       as tenant_id,
    proc_year,
    proc_month,
    emp_no,
    emp_name,
    designation_name,
    category_name,
    hierarchy_name,
    je,
    payroll_group_name,
    basic_salary,
    ot_1_5_rate,
    ot_1_5_hours,
    ot_1_5_amount,
    ot_2_rate,
    ot_2_hours,
    ot_2_amount,
    ot_3_rate,
    ot_3_hours,
    ot_3_amount,
    round((ot_1_5_hours + ot_2_hours + ot_3_hours)::numeric, 2)   as total_ot_hours,
    round((ot_1_5_amount + ot_2_amount + ot_3_amount)::numeric, 2) as total_ot_amount
from grouped