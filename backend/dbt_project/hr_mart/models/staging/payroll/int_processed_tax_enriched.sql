{{ config(materialized='view') }}

with base as (
    select * from {{ ref('stg_processed_tax_data') }}
),

periods as (
    select payroll_period_sk, tenant_id, payroll_year, payroll_month, payroll_half
    from {{ ref('dim_payroll_period') }}
)

select
    b.tenant_id,
    b.source_system,
    b.source_tax_id,
    b.source_emp_id,
    b.source_payroll_group_id,
    p.payroll_period_sk,
    coalesce(b.tax_component_code, b.tax_component_name, 'tax') as tax_type,
    b.taxable_amount                                         as taxable_income,
    b.tax_relief_amount,
    b.tax_percentage,
    b.tax_amount,
    b.annualized_taxable_income,
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
