{{ config(
    materialized='incremental',
    unique_key=['tenant_id', 'source_system', 'source_multi_currency_id'],
    incremental_strategy='delete+insert',
    on_schema_change='sync_all_columns',
    tags=['warehouse', 'warehouse_payroll', 'warehouse_marts']
) }}

with src as (
    select
        m.*,
        (
            make_date(m.processing_year::integer, m.processing_month::integer, 1)
            + interval '1 month - 1 day'
        )::timestamptz                                        as process_timestamp
    from {{ ref('stg_processed_multi_currency_for_emp_sal') }} m
    {% if is_incremental() %}
    where m._source_updated_at >= (
        select coalesce(max(_source_updated_at), '1970-01-01'::timestamptz) - interval '1 hour'
        from {{ this }}
    )
    {% endif %}
),

periods as (
    select payroll_period_sk, tenant_id, payroll_year, payroll_month, payroll_half
    from {{ ref('dim_payroll_period') }}
),

joined as (
    select
        m.tenant_id,
        m.source_system,
        m.source_multi_currency_id,
        emp.employee_sk,
        p.payroll_period_sk,
        m.source_currency,
        m.target_currency,
        m.exchange_rate,
        m.salary_amount,
        m.converted_amount,
        m.process_timestamp,
        m._source_updated_at
    from src m
    inner join periods p
        on p.tenant_id = m.tenant_id
       and p.payroll_year = m.processing_year
       and p.payroll_month = m.processing_month
       and p.payroll_half = coalesce(m.processing_half, 0)
    {{ payroll_employee_lateral_join('m') }}
)

select
    {{ dbt_utils.generate_surrogate_key([
        'tenant_id', 'source_system', 'source_multi_currency_id'
    ]) }}                                                 as processed_multi_currency_sk,
    j.*,
    current_timestamp                                     as _loaded_at
from joined j
