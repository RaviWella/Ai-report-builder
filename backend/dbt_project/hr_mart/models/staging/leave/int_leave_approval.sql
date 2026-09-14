-- int_leave_approval — standard leave approval actions from staging.

{{ config(materialized='view') }}

SELECT
    '{{ target.name }}'::varchar(64)                       AS tenant_id,
    '{{ var("source_system") }}'::varchar(32)              AS source_system,
    a.id                                                   AS source_approval_id,
    a.leave_application_id                                 AS source_application_id,
    'STANDARD'::varchar(32)                                AS leave_source_code,
    a.approver_employee_id                                 AS source_approver_emp_id,
    a.approval_level_code,
    a.approval_status_code                             AS source_approval_status_code,
    LOWER(TRIM(COALESCE(a.approval_status, 'unknown'))) AS approval_status_code,
    a.action_timestamp,
    a.application_status_code,
    COALESCE(a.updated_at, a.created_at, NOW())            AS _source_updated_at,
    a.created_at                                           AS source_created_at,
    a.updated_at                                           AS source_updated_at
FROM {{ source('hr_raw', 'stg_leave_approvals') }} a
WHERE a.id IS NOT NULL
  AND a.leave_application_id IS NOT NULL
