{{ config(
    materialized='incremental',
    unique_key=['tenant_id', 'source_system', 'source_attendance_line_id'],
    incremental_strategy='delete+insert',
    on_schema_change='sync_all_columns',
    tags=['warehouse', 'warehouse_payroll', 'warehouse_marts']
) }}

with src as (
    select * from {{ ref('int_processed_attendance_enriched') }}
    {% if is_incremental() %}
    where _source_updated_at >= (
        select coalesce(max(_source_updated_at), '1970-01-01'::timestamptz) - interval '1 hour'
        from {{ this }}
    )
    {% endif %}
),

joined as (
    select
        s.tenant_id,
        s.source_system,
        s.source_attendance_line_id,
        emp.employee_sk,
        s.payroll_period_sk,
        pg.payroll_group_sk,
        s.attendance_item_type,
        s.attendance_days,
        s.payable_days,
        s.absent_days,
        s.late_days,
        s.nopay_days,
        s.ot_hours,
        s.attendance_amount,
        s.attendance_deduction,
        s.process_timestamp,
        s._source_updated_at
    from src s
    {{ payroll_employee_lateral_join('s') }}
    left join {{ ref('dim_payroll_group') }} pg
        on pg.tenant_id = s.tenant_id
       and pg.source_payroll_group_id = s.source_payroll_group_id
)

select
    {{ dbt_utils.generate_surrogate_key([
        'tenant_id', 'source_system', 'source_attendance_line_id'
    ]) }}                                                 as attendance_payroll_sk,
    j.*,
    current_timestamp                                     as _loaded_at
from joined j
