-- Payroll group master staging (hr_payroll_groups → ETL).

{{ config(materialized='view') }}

select
    '{{ target.name }}'::varchar(64)                       as tenant_id,
    '{{ var("source_system") }}'::varchar(32)              as source_system,
    g.id                                                   as source_payroll_group_id,
    g.payroll_group_name,
    g.legal_entity_id,
    g.currency_code,
    g.payroll_frequency,
    coalesce(g.is_active, true)                            as is_active,
    g.is_available_epf8,
    g.is_available_epf12,
    g.is_available_etf3,
    g.is_available_tax,
    g.is_stamp_duty,
    g.pg_registered_name,
    g.pg_epf_employer_no,
    g.consider_ot_for_payroll,
    g.consider_late_for_payroll,
    g.consider_nopay_for_payroll,
    g.pg_is_multicycle,
    g.pg_cycles_per_month,
    coalesce(g.updated_at, g.created_at, now())            as _source_updated_at
from {{ source('hr_raw', 'hr_payroll_groups') }} g
where g.id is not null
