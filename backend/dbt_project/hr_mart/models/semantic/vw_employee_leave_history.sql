-- vw_employee_leave_history — unified standard leave application history.

{{ config(materialized='view') }}

SELECT
    e.emp_no                                        AS employee_number,
    e.emp_fullname                                  AS employee_name,
    e.department_name                               AS department_name,
    lt.leave_type_name                              AS leave_type,
    lt.leave_type_code,
    ls.status_name                                  AS leave_status,
    src.source_name                                 AS leave_source,
    a.start_date                                    AS leave_start_date,
    a.end_date                                      AS leave_end_date,
    a.request_date                                  AS leave_apply_date,
    a.approval_date,
    a.requested_days,
    a.approved_days,
    a.unpaid_days,
    a.leave_reason_text                             AS leave_reason,
    a.is_hr_approval,
    a.payroll_impacted_flag,
    a.cancelled_flag,
    a.approval_duration_hours
FROM {{ ref('fct_leave_application') }} a
INNER JOIN {{ ref('dim_employee') }} e
    ON e.employee_sk = a.employee_sk
   AND e.is_current = TRUE
LEFT JOIN {{ ref('dim_leave_type') }} lt
    ON lt.leave_type_sk = a.leave_type_sk
   AND lt.is_current = TRUE
LEFT JOIN {{ ref('dim_leave_status') }} ls
    ON ls.leave_status_sk = a.leave_status_sk
LEFT JOIN {{ ref('dim_leave_source') }} src
    ON src.leave_source_sk = a.leave_source_sk
WHERE a.tenant_id = '{{ target.name }}'
