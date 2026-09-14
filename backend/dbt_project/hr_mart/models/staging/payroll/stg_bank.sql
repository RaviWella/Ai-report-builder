{{ config(materialized='view') }}

select
    '{{ target.name }}'::varchar(64)                       as tenant_id,
    '{{ var("source_system") }}'::varchar(32)              as source_system,
    b.id                                                   as source_bank_id,
    nullif(trim(b.bank_code), '')                          as bank_code,
    nullif(trim(b.bank_name), '')                          as bank_name,
    coalesce(b.updated_at, b.created_at, now())            as _source_updated_at
from {{ source('payroll_processed', 'bank') }} b
where b.id is not null
