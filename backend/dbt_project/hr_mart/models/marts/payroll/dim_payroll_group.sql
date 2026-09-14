-- =============================================================================
-- dim_payroll_group
-- Payroll processing groups (from hr_payroll_groups).
-- =============================================================================

{{ config(
    materialized='table',
    tags=['warehouse', 'warehouse_payroll', 'warehouse_marts'],
    indexes=[
        {'columns': ['tenant_id', 'source_payroll_group_id'], 'unique': true}
    ]
) }}

select
    {{ dbt_utils.generate_surrogate_key([
        'tenant_id', 'source_system', 'source_payroll_group_id'
    ]) }}                                                 as payroll_group_sk,

    source_payroll_group_id,
    payroll_group_name,
    legal_entity_id,
    currency_code,
    payroll_frequency,
    is_active,

    tenant_id,
    source_system,
    _source_updated_at,
    current_timestamp                                     as _loaded_at

from {{ ref('stg_hr_payroll_groups') }}
where source_payroll_group_id is not null
