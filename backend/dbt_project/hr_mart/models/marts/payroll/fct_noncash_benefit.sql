{{ config(
    materialized='incremental',
    unique_key=['tenant_id', 'source_system', 'source_noncash_benefit_id'],
    incremental_strategy='delete+insert',
    on_schema_change='sync_all_columns',
    tags=['warehouse', 'warehouse_payroll', 'warehouse_marts']
) }}

with src as (
    select
        nb.*,
        (
            make_date(nb.processing_year::integer, nb.processing_month::integer, 1)
            + interval '1 month - 1 day'
        )::timestamptz                                        as process_timestamp
    from {{ ref('stg_prl_processed_nonecash_benefits') }} nb
    {% if is_incremental() %}
    where nb._source_updated_at >= (
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
        nb.tenant_id,
        nb.source_system,
        nb.source_noncash_benefit_id,
        emp.employee_sk,
        p.payroll_period_sk,
        nb.benefit_name,
        nb.benefit_type,
        nb.benefit_value,
        nb.taxable_value,
        nb.process_timestamp,
        nb._source_updated_at
    from src nb
    inner join periods p
        on p.tenant_id = nb.tenant_id
       and p.payroll_year = nb.processing_year
       and p.payroll_month = nb.processing_month
       and p.payroll_half = coalesce(nb.processing_half, 0)
    {{ payroll_employee_lateral_join('nb') }}
)

select
    {{ dbt_utils.generate_surrogate_key([
        'tenant_id', 'source_system', 'source_noncash_benefit_id'
    ]) }}                                                 as noncash_benefit_sk,
    j.*,
    current_timestamp                                     as _loaded_at
from joined j
