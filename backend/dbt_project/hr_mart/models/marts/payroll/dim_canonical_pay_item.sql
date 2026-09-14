-- =============================================================================
-- dim_canonical_pay_item
-- Tenant-scoped canonical mapping for dynamic payroll items (seed + future API).
-- =============================================================================

{{ config(
    materialized='table',
    tags=['warehouse', 'warehouse_payroll', 'warehouse_marts'],
    indexes=[
        {'columns': ['tenant_id', 'source_item_name'], 'unique': true}
    ]
) }}

{% set tenant = var('tenant_id', target.name) %}

select
    {{ dbt_utils.generate_surrogate_key([
        'tenant_id', 'source_item_name'
    ]) }}                                                 as canonical_pay_item_sk,

    source_item_name,
    canonical_item_name,
    canonical_category,
    payroll_behavior,
    is_taxable,
    is_epf_applicable,
    item_type,

    tenant_id,
    current_timestamp                                     as _loaded_at

from {{ ref('dim_canonical_pay_item_seed') }}
where tenant_id = '{{ tenant }}'
