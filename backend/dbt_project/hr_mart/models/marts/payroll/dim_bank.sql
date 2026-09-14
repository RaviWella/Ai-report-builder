-- Bank master dimension from payroll bank source.

{{ config(
    materialized='table',
    tags=['warehouse', 'warehouse_payroll', 'warehouse_marts'],
    indexes=[
        {'columns': ['tenant_id', 'source_bank_id'], 'unique': true}
    ]
) }}

select
    {{ dbt_utils.generate_surrogate_key([
        'tenant_id', 'source_system', 'source_bank_id'
    ]) }}                                                 as bank_sk,

    source_bank_id,
    bank_code,
    bank_name,

    tenant_id,
    source_system,
    _source_updated_at,
    current_timestamp                                     as _loaded_at
from {{ ref('stg_bank') }}
where source_bank_id is not null
