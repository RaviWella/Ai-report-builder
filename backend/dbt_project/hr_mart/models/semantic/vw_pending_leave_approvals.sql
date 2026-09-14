-- vw_pending_leave_approvals — operational approval queue (standard leave).

{{ config(materialized='view') }}

SELECT
    e.emp_no                                        AS employee_number,
    e.emp_fullname                                  AS employee_name,
    approver.emp_no                                 AS approver_employee_number,
    approver.emp_fullname                           AS approver_name,
    lt.leave_type_name                              AS leave_type,
    app.start_date                                  AS leave_start_date,
    app.end_date                                    AS leave_end_date,
    app.requested_days,
    app.request_date                                AS leave_apply_date,
    a.approval_level_name,
    a.approval_status_code                          AS approval_status,
    a.approval_sequence,
    a.action_date,
    app.leave_reason_text                           AS leave_reason
FROM {{ ref('fct_leave_approval') }} a
INNER JOIN {{ ref('fct_leave_application') }} app
    ON app.leave_application_sk = a.leave_application_sk
INNER JOIN {{ ref('dim_employee') }} e
    ON e.employee_sk = a.applicant_employee_sk
   AND e.is_current = TRUE
LEFT JOIN {{ ref('dim_employee') }} approver
    ON approver.employee_sk = a.approver_employee_sk
   AND approver.is_current = TRUE
LEFT JOIN {{ ref('dim_leave_type') }} lt
    ON lt.leave_type_sk = app.leave_type_sk
   AND lt.is_current = TRUE
WHERE a.tenant_id = '{{ target.name }}'
  AND a.approval_status_code = 'pending'
  AND app.leave_status_code IN ('pending', 'unknown')
