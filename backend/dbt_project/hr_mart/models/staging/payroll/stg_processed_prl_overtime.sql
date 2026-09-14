-- prl_overtime enriched staging (silver) — OT worksheet hours by employee × period.
-- Physical load: hr_raw.stg_prl_overtime (ETL). This view adds tenant metadata.

{{ config(materialized='view') }}

select
    '{{ target.name }}'::varchar(64)                       as tenant_id,
    '{{ var("source_system") }}'::varchar(32)              as source_system,
    o.id                                                   as source_overtime_id,
    o.employee_id                                          as source_emp_id,
    o.proc_year                                            as processing_year,
    o.proc_month                                           as processing_month,
    coalesce(o.proc_half, 0)                               as processing_half,
    o.proc_year,
    o.proc_month,
    {{ payroll_period_label('o.proc_year', 'o.proc_month') }} as period_label,
    coalesce(o.ot_inone_hours, 0)                          as ot_inone_hours,
    coalesce(o.ot_outone_hours, 0)                         as ot_outone_hours,
    coalesce(o.ot_dayorhour_hours, 0)                      as ot_dayorhour_hours,
    coalesce(o.updated_at, o.created_at, now())            as _source_updated_at
from {{ source('payroll_processed', 'prl_overtime') }} o
