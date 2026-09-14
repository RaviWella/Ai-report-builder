-- Bank branch dimension from payroll branch source.

{{ config(
    materialized='table',
    tags=['warehouse', 'warehouse_payroll', 'warehouse_marts'],
    indexes=[
        {'columns': ['tenant_id', 'source_bank_branch_id'], 'unique': true}
    ]
) }}

with src as (
    select * from {{ ref('stg_mas_branch') }}
),
bank as (
    select bank_sk, tenant_id, source_system, source_bank_id
    from {{ ref('dim_bank') }}
)

select
    {{ dbt_utils.generate_surrogate_key([
        's.tenant_id', 's.source_system', 's.source_bank_branch_id'
    ]) }}                                                 as bank_branch_sk,

    s.source_bank_branch_id,
    s.source_bank_id,
    b.bank_sk,
    s.branch_code,
    s.branch_name,

    s.tenant_id,
    s.source_system,
    s._source_updated_at,
    current_timestamp                                     as _loaded_at
from src s
left join bank b
    on b.tenant_id = s.tenant_id
   and b.source_system = s.source_system
   and b.source_bank_id = s.source_bank_id
where s.source_bank_branch_id is not null
