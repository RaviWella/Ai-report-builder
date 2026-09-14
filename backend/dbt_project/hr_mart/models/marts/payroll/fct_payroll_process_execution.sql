-- Payroll run execution metadata (§7.10) from analyze + run headers.

{{ config(materialized='table', tags=['warehouse', 'warehouse_payroll', 'warehouse_marts']) }}

with runs as (
    select * from {{ source('hr_raw', 'stg_payroll_runs') }}
),

salary_analyze as (
    select * from {{ source('hr_raw', 'stg_payroll_salary_analyze') }}
),

periods as (
    select payroll_period_sk, tenant_id, payroll_year, payroll_month, payroll_half
    from {{ ref('dim_payroll_period') }}
),

groups as (
    select payroll_group_sk, tenant_id, source_payroll_group_id
    from {{ ref('dim_payroll_group') }}
),

from_analyze as (
    select
        a.id                                                   as payroll_run_id,
        a.payroll_group_id                                     as source_payroll_group_id,
        a.proc_year                                            as payroll_year,
        a.proc_month                                           as payroll_month,
        coalesce(a.proc_half, 0)                               as payroll_half,
        a.process_start_time,
        a.process_end_time,
        extract(epoch from (a.process_end_time - a.process_start_time))::bigint
                                                               as process_duration_seconds,
        a.processed_employee_count,
        a.failed_employee_count,
        a.reversed_employee_count,
        a.process_type,
        a.process_status,
        a.triggered_by,
        coalesce(a.updated_at, a.created_at, now())            as _source_updated_at
    from salary_analyze a
),

from_runs as (
    select
        r.id                                                   as payroll_run_id,
        {{ payroll_run_group_id('r.id') }}                     as source_payroll_group_id,
        r.payroll_year,
        r.payroll_month,
        coalesce(r.payroll_half, 0)                            as payroll_half,
        coalesce(r.processed_at, r.created_at)                 as process_start_time,
        coalesce(r.updated_at, r.processed_at, r.created_at)   as process_end_time,
        cast(null as bigint)                                   as process_duration_seconds,
        cast(null as integer)                                  as processed_employee_count,
        cast(null as integer)                                  as failed_employee_count,
        cast(null as integer)                                  as reversed_employee_count,
        'payroll_run'::varchar(32)                             as process_type,
        r.status                                               as process_status,
        cast(r.processed_by as varchar)                        as triggered_by,
        coalesce(r.updated_at, r.created_at, now())            as _source_updated_at
    from runs r
),

combined as (
    select * from from_analyze
    union all
    select fr.*
    from from_runs fr
    where not exists (select 1 from from_analyze fa
                      where fa.payroll_year = fr.payroll_year
                        and fa.payroll_month = fr.payroll_month
                        and fa.payroll_half = fr.payroll_half
                        and fa.source_payroll_group_id = fr.source_payroll_group_id)
),

final as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'" ~ target.name ~ "'",
            "'" ~ var('source_system') ~ "'",
            'c.payroll_run_id'
        ]) }}                                                 as payroll_process_execution_sk,
        '{{ target.name }}'::varchar(64)                       as tenant_id,
        '{{ var("source_system") }}'::varchar(32)              as source_system,
        g.payroll_group_sk,
        p.payroll_period_sk,
        c.process_start_time,
        c.process_end_time,
        c.process_duration_seconds,
        c.processed_employee_count,
        c.failed_employee_count,
        c.reversed_employee_count,
        c.process_type,
        c.process_status,
        c.triggered_by,
        c._source_updated_at,
        current_timestamp                                     as _loaded_at
    from combined c
    inner join periods p
        on p.tenant_id = '{{ target.name }}'
       and p.payroll_year = c.payroll_year
       and p.payroll_month = c.payroll_month
       and p.payroll_half = c.payroll_half
    inner join groups g
        on g.tenant_id = '{{ target.name }}'
       and g.source_payroll_group_id = c.source_payroll_group_id
)

select * from final
