-- =============================================================================
-- dim_payroll_period
-- Payroll calendar dimension — one row per (year, month, half) observed in
-- processed payroll snapshots.
-- =============================================================================

{{ config(
    materialized='table',
    tags=['warehouse', 'warehouse_payroll', 'warehouse_marts'],
    indexes=[
        {'columns': ['tenant_id', 'payroll_year', 'payroll_month', 'payroll_half'], 'unique': true}
    ]
) }}

with periods as (
    select distinct
        tenant_id,
        source_system,
        processing_year,
        processing_month,
        coalesce(processing_half, 0)              as processing_half
    from {{ ref('stg_processed_sal_basic_data') }}
    where processing_year is not null
      and processing_month is not null
),

final as (
    select
        {{ dbt_utils.generate_surrogate_key([
            'tenant_id', 'source_system',
            'processing_year', 'processing_month', 'processing_half'
        ]) }}                                                 as payroll_period_sk,

        processing_year                                       as payroll_year,
        processing_month                                      as payroll_month,
        processing_half                                       as payroll_half,

        make_date(processing_year, processing_month, 1)       as period_start_date,
        (
            make_date(processing_year, processing_month, 1)
            + interval '1 month'
            - interval '1 day'
        )::date                                               as period_end_date,

        case
            when processing_half in (1, 2) then 'fortnightly'
            else 'monthly'
        end                                                   as payroll_frequency,

        true                                                  as is_closed,

        tenant_id,
        source_system,
        current_timestamp                                     as _loaded_at

    from periods
)

select * from final
