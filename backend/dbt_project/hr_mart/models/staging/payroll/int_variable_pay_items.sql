-- Enriched variable pay items + non-consider items (§7.5 sources).

{{ config(materialized='view') }}

with base as (
    select
        tenant_id,
        source_system,
        source_variable_item_id                              as source_variable_id,
        item_direction                                       as variable_item_type,
        source_emp_id,
        source_payroll_group_id,
        processing_year,
        processing_month,
        processing_half,
        proc_year,
        proc_month,
        source_component_id,
        item_direction,
        concat(
            item_direction, '_',
            coalesce(source_component_id::text, source_variable_item_id::text)
        )                                                    as variable_item_name,
        amount,
        true                                                 as is_considered_for_payroll,
        _source_updated_at
    from {{ ref('stg_prl_variable_pay_items') }}

    union all

    select
        tenant_id,
        source_system,
        source_variable_item_id                              as source_variable_id,
        item_direction                                       as variable_item_type,
        source_emp_id,
        source_payroll_group_id,
        processing_year,
        processing_month,
        processing_half,
        proc_year,
        proc_month,
        source_component_id,
        item_direction,
        item_name                                            as variable_item_name,
        amount,
        is_considered_for_payroll,
        _source_updated_at
    from {{ ref('stg_processed_non_consider_pay_items') }}
),

periods as (
    select payroll_period_sk, tenant_id, payroll_year, payroll_month, payroll_half
    from {{ ref('dim_payroll_period') }}
),

canonical as (
    select
        tenant_id,
        canonical_pay_item_sk,
        source_item_name,
        canonical_item_name
    from {{ ref('dim_canonical_pay_item') }}
)

select
    b.tenant_id,
    b.source_system,
    b.source_variable_id,
    b.variable_item_type,
    b.source_emp_id,
    b.source_payroll_group_id,
    p.payroll_period_sk,
    c.canonical_pay_item_sk,
    coalesce(
        nullif(trim(c.canonical_item_name), ''),
        nullif(trim(c.source_item_name), ''),
        b.variable_item_name
    )                                                      as variable_item_name,
    b.amount,
    b.is_considered_for_payroll,
    (
        make_date(b.proc_year::integer, b.proc_month::integer, 1)
        + interval '1 month - 1 day'
    )::timestamptz                                          as process_timestamp,
    b._source_updated_at
from base b
inner join periods p
    on p.tenant_id = b.tenant_id
   and p.payroll_year = b.processing_year
   and p.payroll_month = b.processing_month
   and p.payroll_half = coalesce(b.processing_half, 0)
left join canonical c
    on c.tenant_id = b.tenant_id
   and (
        c.source_item_name = b.variable_item_name
        or c.source_item_name = concat('component_', b.source_component_id::text)
        or c.source_item_name = concat(
            b.item_direction, '_component_', b.source_component_id::text
        )
   )
