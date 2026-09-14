{{ config(materialized='view') }}

select
    '{{ target.name }}'::varchar(64)                       as tenant_id,
    '{{ var("source_system") }}'::varchar(32)              as source_system,
    c.id                                                   as source_compliance_id,
    c.payroll_run_id,
    {{ payroll_run_group_id('c.payroll_run_id') }}           as source_payroll_group_id,
    c.employee_id                                          as source_emp_id,
    c.compliance_salary,
    c.compliance_ot,
    c.compliance_nopay,
    c.compliance_attendance_days,
    c.compliance_work_hours,
    c.compliance_status,
    c.proc_year                                            as processing_year,
    c.proc_month                                           as processing_month,
    coalesce(c.proc_half, 0)                               as processing_half,
    coalesce(c.updated_at, c.created_at, now())            as _source_updated_at
from {{ source('payroll_processed', 'processed_sal_basic_data_compliance') }} c
