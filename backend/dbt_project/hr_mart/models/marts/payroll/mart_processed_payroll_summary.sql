-- =============================================================================

-- mart_processed_payroll_summary

-- Primary payroll BI mart — built from warehouse facts only (§8.1).

-- Grain: employee_sk × payroll_period_sk

-- =============================================================================



{{ config(

    materialized='table',

    tags=['warehouse', 'warehouse_payroll', 'warehouse_marts'],

    indexes=[

        {'columns': ['tenant_id', 'employee_sk', 'payroll_period_sk'], 'unique': true}

    ]

) }}



with salary as (

    select * from {{ ref('fct_processed_salary') }}

),



salary_agg as (

    select

        tenant_id,

        employee_sk,

        payroll_period_sk,

        sum(basic_salary)                                     as basic_salary,

        sum(total_additions)                                  as total_additions,

        sum(gross_salary)                                     as gross_salary,

        sum(total_deductions)                                 as total_deductions,

        sum(net_salary)                                       as net_salary,

        sum(tax_amount)                                       as tax_amount,

        sum(epf_employee_amount)                              as epf_employee_amount,

        sum(epf_employer_amount)                              as epf_employer_amount,

        sum(etf_amount)                                       as etf_amount,

        sum(pay_cut_amount)                                   as pay_cut_amount,

        sum(increment_amount)                                 as increment_amount,
        sum(ot_amount)                                        as ot_amount,
        sum(nopay_deduction)                                  as nopay_deduction,
        max(currency_code)                                    as payroll_currency,
        max(process_timestamp)                                as process_timestamp,
        max(process_status)                                   as process_status
    from salary

    group by tenant_id, employee_sk, payroll_period_sk

),



primary_group as (

    select distinct on (tenant_id, employee_sk, payroll_period_sk)

        tenant_id,

        employee_sk,

        payroll_period_sk,

        payroll_group_sk

    from salary

    order by

        tenant_id,

        employee_sk,

        payroll_period_sk,

        net_salary desc nulls last,

        source_processed_salary_id desc

),



emp as (

    select

        employee_sk,

        tenant_id,

        emp_no,

        emp_fullname,

        designation_name,

        employee_category,

        legal_entity_name,

        branch_id,

        payroll_group                                         as employee_payroll_group_id

    from {{ ref('dim_employee') }}

    where is_current = true

),



pg as (

    select * from {{ ref('dim_payroll_group') }}

),



period as (

    select * from {{ ref('dim_payroll_period') }}

)



select

    s.tenant_id,

    s.employee_sk,

    s.payroll_period_sk,

    pgk.payroll_group_sk,



    p.payroll_year,

    p.payroll_month,

    p.payroll_half,

    p.period_start_date,

    p.period_end_date,



    e.emp_no,

    e.emp_fullname,

    e.designation_name                                      as designation,

    e.employee_category,

    e.legal_entity_name                                     as legal_entity,

    cast(e.branch_id as varchar)                            as branch,

    pg.payroll_group_name,



    s.basic_salary,

    s.gross_salary,

    s.total_additions,

    s.total_deductions,

    s.net_salary,

    s.tax_amount,

    s.epf_employee_amount,

    s.epf_employer_amount,

    s.etf_amount,

    s.pay_cut_amount,

    s.increment_amount,
    s.ot_amount,
    s.nopay_deduction,
    s.payroll_currency,

    s.process_status,



    s.process_timestamp,

    current_timestamp                                       as _refreshed_at



from salary_agg s

inner join primary_group pgk

    on  pgk.tenant_id = s.tenant_id

   and pgk.employee_sk = s.employee_sk

   and pgk.payroll_period_sk = s.payroll_period_sk

left join emp e

    on  e.employee_sk = s.employee_sk

    and e.tenant_id   = s.tenant_id

left join pg

    on  pg.payroll_group_sk = pgk.payroll_group_sk

left join period p

    on  p.payroll_period_sk = s.payroll_period_sk


