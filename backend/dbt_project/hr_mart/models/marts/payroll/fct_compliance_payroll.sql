-- Compliance payroll from processed compliance source tables (§7.9).

{{ config(
    materialized='table',
    tags=['warehouse', 'warehouse_payroll', 'warehouse_marts']
) }}

with basic as (
    select
        b.*,
        (
            make_date(b.processing_year::integer, b.processing_month::integer, 1)
            + interval '1 month - 1 day'
        )::timestamptz                                        as process_timestamp
    from {{ ref('stg_processed_sal_basic_data_compliance') }} b
),

periods as (
    select payroll_period_sk, tenant_id, payroll_year, payroll_month, payroll_half
    from {{ ref('dim_payroll_period') }}
),

joined as (
    select
        b.tenant_id,
        b.source_system,
        b.source_compliance_id,
        emp.employee_sk,
        p.payroll_period_sk,
        b.compliance_salary,
        b.compliance_ot,
        b.compliance_nopay,
        b.compliance_attendance_days,
        b.compliance_work_hours,
        b.compliance_status,
        b.process_timestamp,
        b._source_updated_at
    from basic b
    inner join periods p
        on p.tenant_id = b.tenant_id
       and p.payroll_year = b.processing_year
       and p.payroll_month = b.processing_month
       and p.payroll_half = coalesce(b.processing_half, 0)
    {{ payroll_employee_lateral_join('b') }}
)

select
    {{ dbt_utils.generate_surrogate_key([
        'tenant_id', 'source_system', 'source_compliance_id'
    ]) }}                                                 as compliance_payroll_sk,
    j.*,
    current_timestamp                                     as _loaded_at
from joined j
