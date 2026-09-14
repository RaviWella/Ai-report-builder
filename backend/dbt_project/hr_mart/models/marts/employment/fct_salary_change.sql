-- =============================================================================
-- fct_salary_change
-- One row per salary revision from hr_lifecycle. dim_employee join matches
-- fct_lifecycle_event (LATERAL + effective_date PIT fallback).
-- =============================================================================

{{ config(
    materialized='incremental',
    unique_key=['tenant_id', 'source_system', 'source_increment_id'],
    incremental_strategy='delete+insert',
    on_schema_change='sync_all_columns',
    tags=['warehouse', 'warehouse_marts'],
    indexes=[
        {'columns': ['tenant_id', 'employee_sk', 'effective_date'], 'unique': false},
        {'columns': ['tenant_id', 'change_type', 'effective_date'], 'unique': false}
    ]
) }}

with changes as (
    select * from {{ ref('int_salary_change_enriched') }}

    {% if is_incremental() %}
    where _source_updated_at >= (
        select coalesce(max(_source_updated_at), '1970-01-01'::timestamptz)
               - interval '1 hour'
        from {{ this }}
    )
    {% endif %}
),

changes_norm as (
    select
        c.*,
        coalesce(nullif(trim(c.source_system), ''), '{{ var("source_system") }}')
                                                as _source_system_norm
    from changes c
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
        c.tenant_id,
        c._source_system_norm                        as source_system,
        c.source_increment_id,
        c.source_emp_id,

        emp.employee_sk,
        to_char(c.effective_date, 'YYYYMMDD')::integer   as effective_date_sk,
        c.effective_date,

        c.change_type,
        c.previous_salary,
        c.new_salary,
        c.change_amount,
        c.change_pct,

        c.designation_at_change,
        c.grade_at_change,
        c.legal_entity_at_change,

        c.approved_by_emp_id,
        c.approved_date,
        c.reason,
        c.event_name,

        c._source_updated_at,
        current_timestamp                              as _loaded_at

    from changes_norm c

    left join lateral (
        select d.employee_sk
        from employee d
        where trim(d.tenant_id::text) = trim(c.tenant_id::text)
          and d.source_system_norm = c._source_system_norm
          and d.source_emp_id = c.source_emp_id
        order by
            case
                when c.effective_date >= ((d.valid_from at time zone 'UTC'))::date
                 and c.effective_date < ((d.valid_to at time zone 'UTC'))::date
                then 0 else 1
            end,
            case when d.is_current then 0 else 1 end,
            d.valid_from desc
        limit 1
    ) emp on true
)

select * from final
