-- =============================================================================
-- fct_lifecycle_event
-- One row per career lifecycle event. dim_employee join uses LATERAL with PIT
-- preference on effective_date, then is_current, then latest version — same
-- pattern as fct_daily_attendance (SCD valid_from reflects load time, not HR date).
-- =============================================================================

{{ config(
    materialized='incremental',
    unique_key=['tenant_id', 'source_system', 'source_lifecycle_id'],
    incremental_strategy='delete+insert',
    on_schema_change='sync_all_columns',
    tags=['warehouse', 'warehouse_marts'],
    indexes=[
        {'columns': ['tenant_id', 'employee_sk', 'effective_date'], 'unique': false},
        {'columns': ['tenant_id', 'event_category', 'effective_date'], 'unique': false}
    ]
) }}

with events as (
    select * from {{ ref('int_lifecycle_event_enriched') }}

    {% if is_incremental() %}
    where _source_updated_at >= (
        select coalesce(max(_source_updated_at), '1970-01-01'::timestamptz)
               - interval '1 hour'
        from {{ this }}
    )
    {% endif %}
),

events_norm as (
    select
        e.*,
        coalesce(nullif(trim(e.source_system), ''), '{{ var("source_system") }}')
                                                as _source_system_norm
    from events e
),

employee as (
    select
        employee_sk,
        tenant_id,
        coalesce(nullif(trim(source_system::text), ''), '{{ var("source_system") }}')
                                                as source_system_norm,
        source_emp_id,
        valid_from,
        valid_to,
        is_current
    from {{ ref('dim_employee') }}
),

final as (
    select
        e.tenant_id,
        e._source_system_norm                        as source_system,
        e.source_lifecycle_id,
        e.source_emp_id,

        emp.employee_sk,
        to_char(e.effective_date, 'YYYYMMDD')::integer   as effective_date_sk,
        e.effective_date,

        e.event_category,
        e.event_name,
        e.source_position_id,

        e.previous_designation,
        e.new_designation,
        e.previous_grade,
        e.new_grade,
        e.previous_location,
        e.new_location,
        e.new_legal_entity,
        e.new_company_section,
        e.new_section,

        e.new_salary,
        e.previous_salary,
        e.reason,
        e.triggered_by_emp_id,
        e.approved_date,
        e.last_working_date,
        e.parent_source_lifecycle_id,

        e._source_updated_at,
        current_timestamp                              as _loaded_at

    from events_norm e

    left join lateral (
        select d.employee_sk
        from employee d
        where trim(d.tenant_id::text) = trim(e.tenant_id::text)
          and d.source_system_norm = e._source_system_norm
          and d.source_emp_id = e.source_emp_id
        order by
            case
                when e.effective_date >= ((d.valid_from at time zone 'UTC'))::date
                 and e.effective_date < ((d.valid_to at time zone 'UTC'))::date
                then 0 else 1
            end,
            case when d.is_current then 0 else 1 end,
            d.valid_from desc
        limit 1
    ) emp on true
)

select * from final
