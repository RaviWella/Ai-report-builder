-- Variable additions + deductions (unioned dynamic pay items).

{{ config(materialized='view') }}

with additions as (
    select
        '{{ target.name }}'::varchar(64)                       as tenant_id,
        '{{ var("source_system") }}'::varchar(32)              as source_system,
        va.id                                                  as source_variable_item_id,
        va.payroll_run_id,
        {{ payroll_run_group_id('va.payroll_run_id') }}          as source_payroll_group_id,
        va.employee_id                                         as source_emp_id,
        va.proc_year                                       as processing_year,
        va.proc_month                                      as processing_month,
        coalesce(va.proc_half, 0)                          as processing_half,
        va.proc_year,
        va.proc_month,
        {{ payroll_period_label('va.proc_year', 'va.proc_month') }}
                                                               as period_label,
        va.ref_component_id                                    as source_component_id,
        'addition'::varchar(16)                                as item_direction,
        va.quantity,
        va.rate,
        va.amount,
        coalesce(va.updated_at, va.created_at, now())          as _source_updated_at
    from {{ source('payroll_processed', 'prl_variableadditions_forsal') }} va
),

deductions as (
    select
        '{{ target.name }}'::varchar(64)                       as tenant_id,
        '{{ var("source_system") }}'::varchar(32)              as source_system,
        vd.id                                                  as source_variable_item_id,
        vd.payroll_run_id,
        {{ payroll_run_group_id('vd.payroll_run_id') }}          as source_payroll_group_id,
        vd.employee_id                                         as source_emp_id,
        vd.proc_year                                       as processing_year,
        vd.proc_month                                      as processing_month,
        coalesce(vd.proc_half, 0)                          as processing_half,
        vd.proc_year,
        vd.proc_month,
        {{ payroll_period_label('vd.proc_year', 'vd.proc_month') }}
                                                               as period_label,
        vd.ref_component_id                                    as source_component_id,
        'deduction'::varchar(16)                               as item_direction,
        vd.quantity,
        vd.rate,
        vd.amount,
        coalesce(vd.updated_at, vd.created_at, now())          as _source_updated_at
    from {{ source('payroll_processed', 'prl_variabledeductions_forsal') }} vd
)

select * from additions
union all
select * from deductions
