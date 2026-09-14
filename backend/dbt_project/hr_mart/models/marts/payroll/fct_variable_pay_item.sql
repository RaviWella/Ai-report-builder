-- Dynamic variable additions/deductions fact.

{{ config(
    materialized='incremental',
    unique_key=['tenant_id', 'source_system', 'source_variable_id', 'variable_item_type'],
    incremental_strategy='delete+insert',
    on_schema_change='sync_all_columns',
    tags=['warehouse', 'warehouse_payroll', 'warehouse_marts']
) }}

with src as (
    select * from {{ ref('int_variable_pay_items') }}

    {% if is_incremental() %}
    where _source_updated_at >= (
        select coalesce(max(_source_updated_at), '1970-01-01'::timestamptz) - interval '1 hour'
        from {{ this }}
    )
    {% endif %}
),

joined as (
    select
        s.tenant_id,
        s.source_system,
        s.source_variable_id,
        s.variable_item_type,
        s.source_emp_id,
        s.source_payroll_group_id,
        emp.employee_sk,
        s.payroll_period_sk,
        s.canonical_pay_item_sk,
        s.variable_item_name,
        s.amount,
        s.is_considered_for_payroll,
        s.process_timestamp,
        s._source_updated_at,
        current_timestamp                                       as _loaded_at
    from src s
    {{ payroll_employee_lateral_join('s') }}
)

select
    {{ dbt_utils.generate_surrogate_key([
        'tenant_id', 'source_system', 'source_variable_id', 'variable_item_type'
    ]) }}                                                     as variable_pay_item_sk,
    j.*
from joined j
