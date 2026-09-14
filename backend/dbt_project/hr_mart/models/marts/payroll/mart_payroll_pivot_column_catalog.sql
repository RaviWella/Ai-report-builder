-- Catalog of dynamic paysheet columns (for reports / API discovery).

{{ config(materialized='table', tags=['warehouse', 'warehouse_payroll', 'warehouse_marts']) }}

select
    tenant_id,
    pivot_key,
    max(pivot_label)                                          as pivot_label,
    max(pivot_type)                                           as pivot_type,
    count(*)                                                  as line_count,
    count(distinct employee_sk)                               as employee_count,
    sum(amount)                                               as total_amount,
    current_timestamp                                         as _refreshed_at
from {{ ref('int_payroll_paysheet_vertical') }}
group by tenant_id, pivot_key
order by tenant_id, pivot_key
