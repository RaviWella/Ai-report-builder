{{ config(materialized='view') }}

select
    '{{ target.name }}'::varchar(64)                       as tenant_id,
    '{{ var("source_system") }}'::varchar(32)              as source_system,
    mb.id                                                  as source_bank_branch_id,
    mb.ref_bank_id                                         as source_bank_id,
    nullif(trim(mb.branch_code), '')                       as branch_code,
    nullif(trim(mb.branch_name), '')                       as branch_name,
    coalesce(mb.updated_at, mb.created_at, now())          as _source_updated_at
from {{ source('payroll_processed', 'mas_branch') }} mb
where mb.id is not null
