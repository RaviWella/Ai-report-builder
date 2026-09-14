-- Dynamic payroll item analytics mart (§8.3).

{{ config(materialized='table', tags=['warehouse', 'warehouse_payroll', 'warehouse_marts']) }}

with variable as (
    select
        tenant_id,
        payroll_period_sk,
        canonical_pay_item_sk,
        variable_item_name,
        count(distinct employee_sk)                           as employee_count,
        sum(amount)                                           as total_amount,
        avg(amount)                                           as avg_amount,
        max(amount)                                           as max_amount,
        min(amount)                                           as min_amount
    from {{ ref('fct_variable_pay_item') }}
    group by 1, 2, 3, 4
),

add_ded as (
    select
        tenant_id,
        payroll_period_sk,
        canonical_pay_item_sk,
        payroll_item_name                                     as variable_item_name,
        count(distinct employee_sk)                           as employee_count,
        sum(amount)                                           as total_amount,
        avg(amount)                                           as avg_amount,
        max(amount)                                           as max_amount,
        min(amount)                                           as min_amount
    from {{ ref('fct_processed_add_ded') }}
    group by 1, 2, 3, 4
),

combined as (
    select * from variable
    union all
    select * from add_ded
)

select
    c.*,
    current_timestamp                                       as _refreshed_at
from combined c
