{{ config(
    materialized='incremental',
    unique_key=['tenant_id', 'source_system', 'source_tax_id'],
    incremental_strategy='delete+insert',
    on_schema_change='sync_all_columns',
    tags=['warehouse', 'warehouse_payroll', 'warehouse_marts']
) }}

with src as (
    select * from {{ ref('int_processed_tax_enriched') }}
    {% if is_incremental() %}
    where _source_updated_at >= (
        select coalesce(max(_source_updated_at), '1970-01-01'::timestamptz) - interval '1 hour'
        from {{ this }}
    )
    {% endif %}
),

joined as (
    select
        t.tenant_id,
        t.source_system,
        t.source_tax_id,
        emp.employee_sk,
        t.payroll_period_sk,
        t.tax_type,
        t.taxable_income,
        t.tax_relief_amount,
        t.tax_percentage,
        t.tax_amount,
        t.annualized_taxable_income,
        t.process_timestamp,
        t._source_updated_at
    from src t
    {{ payroll_employee_lateral_join('t') }}
)

select
    {{ dbt_utils.generate_surrogate_key([
        'tenant_id', 'source_system', 'source_tax_id'
    ]) }}                                                 as processed_tax_sk,
    j.*,
    current_timestamp                                     as _loaded_at
from joined j
