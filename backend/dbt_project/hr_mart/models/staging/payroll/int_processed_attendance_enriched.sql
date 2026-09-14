{{ config(materialized='view') }}

with base as (
    select * from {{ ref('stg_processed_sal_attendance') }}
),

periods as (
    select payroll_period_sk, tenant_id, payroll_year, payroll_month, payroll_half
    from {{ ref('dim_payroll_period') }}
)

select
    b.tenant_id,
    b.source_system,
    b.source_attendance_line_id,
    b.source_emp_id,
    b.source_payroll_group_id,
    p.payroll_period_sk,
    coalesce(b.line_type_name, b.line_type)                  as attendance_item_type,
    cast(null as numeric(14, 2))                             as attendance_days,
    cast(null as numeric(14, 2))                             as payable_days,
    cast(null as numeric(14, 2))                             as absent_days,
    cast(null as numeric(14, 2))                             as late_days,
    case
        when lower(coalesce(b.line_type_name, '')) like '%no pay%'
          or lower(coalesce(b.line_type_name, '')) like '%nopay%'
        then coalesce(b.amount, 0)
        else 0
    end                                                      as nopay_days,
    case
        when lower(coalesce(b.line_type_name, '')) like '%overtime%'
          or lower(coalesce(b.line_type_name, '')) like '% ot%'
        then coalesce(b.amount, 0)
        else 0
    end                                                      as ot_hours,
    b.amount                                                 as attendance_amount,
    case
        when lower(coalesce(b.line_type_name, '')) like '%late%'
          or lower(coalesce(b.line_type_name, '')) like '%absent%'
        then coalesce(b.amount, 0)
        else 0
    end                                                      as attendance_deduction,
    (
        make_date(b.proc_year::integer, b.proc_month::integer, 1)
        + interval '1 month - 1 day'
    )::timestamptz                                           as process_timestamp,
    b._source_updated_at
from base b
inner join periods p
    on p.tenant_id = b.tenant_id
   and p.payroll_year = b.processing_year
   and p.payroll_month = b.processing_month
   and p.payroll_half = coalesce(b.processing_half, 0)
