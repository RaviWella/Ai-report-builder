-- Enriched processed add/ded lines with period SK and canonical-ready item names.

{{ config(materialized='view') }}

with base as (
    select * from {{ ref('stg_processed_sal_add_ded') }}
),

periods as (
    select
        payroll_period_sk,
        tenant_id,
        payroll_year,
        payroll_month,
        payroll_half
    from {{ ref('dim_payroll_period') }}
)

select
    b.tenant_id,
    b.source_system,
    b.source_add_ded_id,
    b.source_emp_id,
    b.source_payroll_group_id,
    p.payroll_period_sk,
    coalesce(nullif(trim(b.component_name), ''), nullif(trim(b.line_type_name), ''))
                                                            as payroll_item_name,
    b.line_type                                             as payroll_item_code,
    b.component_direction                                   as add_ded_type,
    b.amount,
    cast(null as numeric(14, 4))                          as quantity,
    cast(null as numeric(14, 4))                          as rate,
    coalesce(b.is_epf_liable, false)                      as is_epf_applicable,
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
