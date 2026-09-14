-- Vertical additions/deductions fact from processed_sal_add_ded.

{{ config(
    materialized='incremental',
    unique_key=['tenant_id', 'source_system', 'source_add_ded_id'],
    incremental_strategy='delete+insert',
    on_schema_change='sync_all_columns',
    tags=['warehouse', 'warehouse_payroll', 'warehouse_marts']
) }}

with src as (
    select * from {{ ref('int_processed_add_ded_enriched') }}

    {% if is_incremental() %}
    where _source_updated_at >= (
        select coalesce(max(_source_updated_at), '1970-01-01'::timestamptz) - interval '1 hour'
        from {{ this }}
    )
    {% endif %}
),

canonical as (
    select * from {{ ref('dim_canonical_pay_item') }}
),

joined as (
    select
        s.tenant_id,
        s.source_system,
        s.source_add_ded_id,
        s.source_emp_id,
        s.source_payroll_group_id,
        emp.employee_sk,
        s.payroll_period_sk,
        pg.payroll_group_sk,
        c.canonical_pay_item_sk,
        s.payroll_item_name,
        s.payroll_item_code,
        s.add_ded_type,
        s.amount,
        s.quantity,
        s.rate,
        s.is_epf_applicable,
        s.process_timestamp,
        s._source_updated_at,
        current_timestamp                                       as _loaded_at
    from src s
    {{ payroll_employee_lateral_join('s') }}
    left join {{ ref('dim_payroll_group') }} pg
        on pg.tenant_id = s.tenant_id
       and pg.source_payroll_group_id = s.source_payroll_group_id
    left join canonical c
        on  c.tenant_id = s.tenant_id
        and c.source_item_name = s.payroll_item_name
)

select
    {{ dbt_utils.generate_surrogate_key([
        'tenant_id', 'source_system', 'source_add_ded_id'
    ]) }}                                                     as processed_add_ded_sk,
    j.*
from joined j
