{{ config(
    materialized='incremental',
    unique_key=['tenant_id', 'source_system', 'source_loan_deduction_id'],
    incremental_strategy='delete+insert',
    on_schema_change='sync_all_columns',
    tags=['warehouse', 'warehouse_payroll', 'warehouse_marts']
) }}

with src as (
    select
        ln.*,
        (
            make_date(ln.proc_year::integer, ln.proc_month::integer, 1)
            + interval '1 month - 1 day'
        )::timestamptz                                        as process_timestamp
    from {{ ref('stg_processed_loan_deduction') }} ln
    {% if is_incremental() %}
    where ln._source_updated_at >= (
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
        ln.tenant_id,
        ln.source_system,
        ln.source_loan_deduction_id,
        emp.employee_sk,
        p.payroll_period_sk,
        pg.payroll_group_sk,
        ln.loan_id,
        ln.installment_id,
        ln.installment_no,
        ln.amount                                             as installment_amount,
        ln.remaining_balance,
        ln.is_final_installment,
        ln.deduction_type,
        ln.deduction_name,
        ln.process_timestamp,
        ln._source_updated_at
    from src ln
    {{ payroll_employee_lateral_join('ln') }}
    inner join periods p
        on p.tenant_id = ln.tenant_id
       and p.payroll_year = ln.processing_year
       and p.payroll_month = ln.processing_month
       and p.payroll_half = coalesce(ln.processing_half, 0)
    left join {{ ref('dim_payroll_group') }} pg
        on pg.tenant_id = ln.tenant_id
       and pg.source_payroll_group_id = ln.source_payroll_group_id
)

select
    {{ dbt_utils.generate_surrogate_key([
        'tenant_id', 'source_system', 'source_loan_deduction_id'
    ]) }}                                                 as processed_loan_sk,
    j.*,
    current_timestamp                                     as _loaded_at
from joined j
