{{ config(materialized='view') }}

select
    '{{ target.name }}'::varchar(64)                       as tenant_id,
    '{{ var("source_system") }}'::varchar(32)              as source_system,
    d.id                                                   as source_salary_bank_data_id,
    d.ref_retrieve_id                                      as source_salary_retrieve_id,
    d.bank_id                                              as source_bank_id,
    d.bank_branch_id                                       as source_bank_branch_id,
    nullif(trim(d.bank_acc_no), '')                        as bank_acc_no,
    coalesce(d.bank_amount, 0)                             as bank_amount,
    nullif(trim(d.bank_passbook_name), '')                 as bank_passbook_name,
    coalesce(d.is_primary_account, false)                  as is_primary_account,
    coalesce(d.updated_at, d.created_at, now())            as _source_updated_at
from {{ source('payroll_processed', 'prl_salary_bank_data') }} d
where d.id is not null
