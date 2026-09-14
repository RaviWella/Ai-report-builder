-- Unified vertical pay lines (fixed add/ded + variable) with stable pivot_key per component.

{{ config(materialized='view', tags=['payroll', 'warehouse_payroll']) }}

with add_ded as (
    select
        a.tenant_id,
        a.employee_sk,
        a.payroll_period_sk,
        a.payroll_item_name,
        a.add_ded_type,
        a.amount,
        c.canonical_item_name,
        c.item_type                                              as canonical_item_type
    from {{ ref('fct_processed_add_ded') }} a
    left join {{ ref('dim_canonical_pay_item') }} c
        on  c.tenant_id = a.tenant_id
        and c.source_item_name = a.payroll_item_name
    where a.employee_sk is not null
      and a.payroll_period_sk is not null
),

variable as (
    select
        v.tenant_id,
        v.employee_sk,
        v.payroll_period_sk,
        v.variable_item_name                                     as payroll_item_name,
        v.variable_item_type                                     as add_ded_type,
        v.amount,
        c.canonical_item_name,
        c.item_type                                              as canonical_item_type
    from {{ ref('fct_variable_pay_item') }} v
    left join {{ ref('dim_canonical_pay_item') }} c
        on  c.tenant_id = v.tenant_id
        and c.source_item_name = v.variable_item_name
    where v.employee_sk is not null
      and v.payroll_period_sk is not null
),

unioned as (
    select * from add_ded
    union all
    select * from variable
),

labeled as (
    select
        u.*,
        coalesce(
            nullif(trim(u.canonical_item_name), ''),
            nullif(trim(u.payroll_item_name), '')
        )                                                        as pivot_label,
        coalesce(
            nullif(trim(u.canonical_item_type), ''),
            nullif(trim(u.add_ded_type), ''),
            'item'
        )                                                        as pivot_type
    from unioned u
    where coalesce(u.amount, 0) <> 0
)

select
    tenant_id,
    employee_sk,
    payroll_period_sk,
    payroll_item_name,
    add_ded_type,
    amount,
    canonical_item_name,
    pivot_label,
    pivot_type,
    payroll_item_name                                         as source_item_name,
    lower(
        regexp_replace(
            regexp_replace(
                pivot_type || '__' || coalesce(pivot_label, payroll_item_name, 'unknown'),
                '[^a-zA-Z0-9]+',
                '_',
                'g'
            ),
            '^_+|_+$',
            '',
            'g'
        )
    )                                                            as pivot_key
from labeled
where coalesce(nullif(trim(pivot_label), ''), nullif(trim(payroll_item_name), '')) is not null
