-- Salary bank payment instructions by employee and payroll period.

{{ config(
    materialized='incremental',
    unique_key=['tenant_id', 'source_system', 'source_salary_bank_data_id', 'payroll_period_sk'],
    incremental_strategy='delete+insert',
    on_schema_change='sync_all_columns',
    tags=['warehouse', 'warehouse_payroll', 'warehouse_marts']
) }}

with retrieve as (
    select * from {{ ref('stg_prl_salary_retrieve') }}
),
bank_data as (
    select * from {{ ref('stg_prl_salary_bank_data') }}
),
salary as (
    select
        tenant_id,
        source_system,
        source_emp_id,
        payroll_period_sk,
        payroll_group_sk,
        process_year,
        process_month,
        process_half,
        payroll_run_id,
        _source_updated_at
    from {{ ref('fct_processed_salary') }}
),
joined as (
    select
        d.tenant_id,
        d.source_system,
        d.source_salary_bank_data_id,
        d.source_salary_retrieve_id,
        r.source_emp_id,
        s.payroll_period_sk,
        s.payroll_group_sk,
        d.source_bank_id,
        d.source_bank_branch_id,
        d.bank_acc_no,
        d.bank_amount,
        d.bank_passbook_name,
        d.is_primary_account,
        r.is_bank,
        greatest(
            coalesce(d._source_updated_at, '1970-01-01'::timestamptz),
            coalesce(r._source_updated_at, '1970-01-01'::timestamptz),
            coalesce(s._source_updated_at, '1970-01-01'::timestamptz)
        )                                                   as _source_updated_at
    from bank_data d
    inner join retrieve r
        on r.tenant_id = d.tenant_id
       and r.source_system = d.source_system
       and r.source_salary_retrieve_id = d.source_salary_retrieve_id
    inner join salary s
        on s.tenant_id = r.tenant_id
       and s.source_system = r.source_system
       and s.source_emp_id = r.source_emp_id
       and (
            nullif(r.payroll_run_id, 0) is null
            or s.payroll_run_id = nullif(r.payroll_run_id, 0)
       )
       and (
            nullif(r.processing_year, 0) is null
            or s.process_year = nullif(r.processing_year, 0)
       )
       and (
            nullif(r.processing_month, 0) is null
            or s.process_month = nullif(r.processing_month, 0)
       )
       and (
            nullif(r.processing_half, 0) is null
            or s.process_half = nullif(r.processing_half, 0)
       )
    {% if is_incremental() %}
    where greatest(
            coalesce(d._source_updated_at, '1970-01-01'::timestamptz),
            coalesce(r._source_updated_at, '1970-01-01'::timestamptz),
            coalesce(s._source_updated_at, '1970-01-01'::timestamptz)
        ) >= (
            select coalesce(max(_source_updated_at), '1970-01-01'::timestamptz) - interval '1 hour'
            from {{ this }}
        )
    {% endif %}
),
bank as (
    select bank_sk, tenant_id, source_system, source_bank_id
    from {{ ref('dim_bank') }}
),
branch as (
    select bank_branch_sk, tenant_id, source_system, source_bank_branch_id
    from {{ ref('dim_bank_branch') }}
),
employees as (
    select employee_sk, tenant_id, source_system, source_emp_id
    from {{ ref('dim_employee') }}
    where is_current = true
)

select
    {{ dbt_utils.generate_surrogate_key([
        'j.tenant_id', 'j.source_system', 'j.source_salary_bank_data_id', 'j.payroll_period_sk'
    ]) }}                                                 as salary_bank_instruction_sk,
    j.tenant_id,
    j.source_system,
    j.source_salary_bank_data_id,
    j.source_salary_retrieve_id,
    e.employee_sk,
    j.source_emp_id,
    j.payroll_period_sk,
    j.payroll_group_sk,
    b.bank_sk,
    br.bank_branch_sk,
    j.source_bank_id,
    j.source_bank_branch_id,
    j.bank_acc_no,
    j.bank_amount,
    j.bank_passbook_name,
    j.is_primary_account,
    j.is_bank,
    j._source_updated_at,
    current_timestamp                                     as _loaded_at
from joined j
left join employees e
    on e.tenant_id = j.tenant_id
   and e.source_system = j.source_system
   and e.source_emp_id = j.source_emp_id
left join bank b
    on b.tenant_id = j.tenant_id
   and b.source_system = j.source_system
   and b.source_bank_id = j.source_bank_id
left join branch br
    on br.tenant_id = j.tenant_id
   and br.source_system = j.source_system
   and br.source_bank_branch_id = j.source_bank_branch_id
