-- int_leave_application — unified leave application headers (all implemented modules).

{{ config(materialized='view') }}

{% set tenant_id = target.name %}
{% set source_system = var('source_system') %}

WITH standard AS (
    SELECT
        '{{ tenant_id }}'::varchar(64)                       AS tenant_id,
        '{{ source_system }}'::varchar(32)                   AS source_system,
        r.id                                                 AS source_application_id,
        'STANDARD'::varchar(32)                              AS leave_source_code,
        r.employee_id                                        AS source_emp_id,
        r.leave_type_id                                      AS source_leave_type_id,
        LOWER(TRIM(COALESCE(r.status, 'unknown')))           AS leave_status_code,
        r.status_code                                        AS source_status_code,
        r.final_status_code                                  AS source_final_status_code,
        r.start_date,
        r.end_date,
        r.request_date,
        r.approval_date,
        COALESCE(r.days_requested, 0)::numeric(8, 2)         AS requested_days,
        COALESCE(r.days_approved, 0)::numeric(8, 2)          AS approved_days,
        r.reason                                             AS leave_reason_text,
        r.purpose_id                                         AS source_purpose_id,
        r.approved_by                                        AS source_approved_by,
        COALESCE(r.is_hr_approval, FALSE)                    AS is_hr_approval,
        COALESCE(r.updated_at, r.created_at, NOW())          AS _source_updated_at,
        r.created_at                                         AS source_created_at,
        r.updated_at                                         AS source_updated_at
    FROM {{ source('hr_raw', 'stg_leave_requests') }} r
    WHERE r.id IS NOT NULL
      AND r.employee_id IS NOT NULL
      AND r.start_date IS NOT NULL
      AND r.end_date IS NOT NULL
),

short_leave AS (
    SELECT
        '{{ tenant_id }}'::varchar(64)                       AS tenant_id,
        '{{ source_system }}'::varchar(32)                   AS source_system,
        s.id                                                 AS source_application_id,
        'SHORT'::varchar(32)                                 AS leave_source_code,
        s.employee_id                                        AS source_emp_id,
        s.leave_type_id                                      AS source_leave_type_id,
        LOWER(TRIM(COALESCE(s.status, 'unknown')))           AS leave_status_code,
        s.status_code                                        AS source_status_code,
        s.final_status_code                                  AS source_final_status_code,
        s.short_leave_date                                   AS start_date,
        s.short_leave_date                                   AS end_date,
        s.request_date,
        s.approval_date,
        GREATEST(COALESCE(s.duration_hours, 0) / 8.0, 0.125)::numeric(8, 2)
                                                             AS requested_days,
        CASE
            WHEN LOWER(TRIM(COALESCE(s.status, ''))) = 'approved'
            THEN GREATEST(COALESCE(s.duration_hours, 0) / 8.0, 0.125)::numeric(8, 2)
            ELSE 0::numeric(8, 2)
        END                                                  AS approved_days,
        s.purpose                                            AS leave_reason_text,
        NULL::integer                                        AS source_purpose_id,
        NULL::integer                                        AS source_approved_by,
        FALSE                                                AS is_hr_approval,
        COALESCE(s.updated_at, s.created_at, NOW())          AS _source_updated_at,
        s.created_at                                         AS source_created_at,
        s.updated_at                                         AS source_updated_at
    FROM {{ source('hr_raw', 'stg_short_leave') }} s
    WHERE s.id IS NOT NULL
      AND s.employee_id IS NOT NULL
      AND s.short_leave_date IS NOT NULL
),

lieu_leave AS (
    SELECT
        '{{ tenant_id }}'::varchar(64)                       AS tenant_id,
        '{{ source_system }}'::varchar(32)                   AS source_system,
        l.id                                                 AS source_application_id,
        'LIEU'::varchar(32)                                  AS leave_source_code,
        l.employee_id                                        AS source_emp_id,
        NULL::integer                                        AS source_leave_type_id,
        LOWER(TRIM(COALESCE(l.status, 'unknown')))           AS leave_status_code,
        l.status_code                                        AS source_status_code,
        l.final_status_code                                  AS source_final_status_code,
        l.leave_date                                         AS start_date,
        l.leave_date                                         AS end_date,
        l.request_date,
        l.approval_date,
        COALESCE(l.leave_day_count, 0)::numeric(8, 2)        AS requested_days,
        CASE
            WHEN LOWER(TRIM(COALESCE(l.status, ''))) = 'approved'
            THEN COALESCE(l.leave_day_count, 0)::numeric(8, 2)
            ELSE 0::numeric(8, 2)
        END                                                  AS approved_days,
        l.purpose                                            AS leave_reason_text,
        NULL::integer                                        AS source_purpose_id,
        NULL::integer                                        AS source_approved_by,
        FALSE                                                AS is_hr_approval,
        COALESCE(l.updated_at, l.created_at, NOW())          AS _source_updated_at,
        l.created_at                                         AS source_created_at,
        l.updated_at                                         AS source_updated_at
    FROM {{ source('hr_raw', 'stg_lieu_leave') }} l
    WHERE l.id IS NOT NULL
      AND l.employee_id IS NOT NULL
      AND l.leave_date IS NOT NULL
),

maternity AS (
    SELECT
        '{{ tenant_id }}'::varchar(64)                       AS tenant_id,
        '{{ source_system }}'::varchar(32)                   AS source_system,
        m.id                                                 AS source_application_id,
        'MATERNITY'::varchar(32)                             AS leave_source_code,
        m.employee_id                                        AS source_emp_id,
        m.leave_type_id                                      AS source_leave_type_id,
        LOWER(TRIM(COALESCE(m.status, 'unknown')))           AS leave_status_code,
        m.status_code                                        AS source_status_code,
        NULL::integer                                        AS source_final_status_code,
        m.start_date,
        COALESCE(m.end_date, m.expected_end_date, m.start_date) AS end_date,
        m.request_date,
        m.approval_date,
        GREATEST(
            (COALESCE(m.end_date, m.expected_end_date, m.start_date) - m.start_date) + 1,
            0
        )::numeric(8, 2)                                     AS requested_days,
        CASE
            WHEN LOWER(TRIM(COALESCE(m.status, ''))) = 'approved'
            THEN GREATEST(
                (COALESCE(m.end_date, m.expected_end_date, m.start_date) - m.start_date) + 1,
                0
            )::numeric(8, 2)
            ELSE 0::numeric(8, 2)
        END                                                  AS approved_days,
        m.purpose                                            AS leave_reason_text,
        NULL::integer                                        AS source_purpose_id,
        NULL::integer                                        AS source_approved_by,
        FALSE                                                AS is_hr_approval,
        COALESCE(m.updated_at, m.created_at, NOW())          AS _source_updated_at,
        m.created_at                                         AS source_created_at,
        m.updated_at                                         AS source_updated_at
    FROM {{ source('hr_raw', 'stg_maternity_leave') }} m
    WHERE m.id IS NOT NULL
      AND m.employee_id IS NOT NULL
      AND m.start_date IS NOT NULL
),

planner AS (
    SELECT
        '{{ tenant_id }}'::varchar(64)                       AS tenant_id,
        '{{ source_system }}'::varchar(32)                   AS source_system,
        p.id                                                 AS source_application_id,
        'PLANNER'::varchar(32)                               AS leave_source_code,
        p.employee_id                                        AS source_emp_id,
        p.leave_type_id                                      AS source_leave_type_id,
        LOWER(TRIM(COALESCE(p.planner_status, 'unknown')))   AS leave_status_code,
        p.planner_status_code                                AS source_status_code,
        NULL::integer                                        AS source_final_status_code,
        p.planned_start_date                                 AS start_date,
        p.planned_end_date                                   AS end_date,
        p.request_date,
        p.approval_date,
        COALESCE(p.planned_days, 0)::numeric(8, 2)           AS requested_days,
        CASE
            WHEN LOWER(TRIM(COALESCE(p.planner_status, ''))) = 'approved'
            THEN COALESCE(p.planned_days, 0)::numeric(8, 2)
            ELSE 0::numeric(8, 2)
        END                                                  AS approved_days,
        p.purpose                                            AS leave_reason_text,
        NULL::integer                                        AS source_purpose_id,
        NULL::integer                                        AS source_approved_by,
        FALSE                                                AS is_hr_approval,
        COALESCE(p.updated_at, p.created_at, NOW())          AS _source_updated_at,
        p.created_at                                         AS source_created_at,
        p.updated_at                                         AS source_updated_at
    FROM {{ source('hr_raw', 'stg_leave_planner') }} p
    WHERE p.id IS NOT NULL
      AND p.employee_id IS NOT NULL
      AND p.planned_start_date IS NOT NULL
      AND p.planned_end_date IS NOT NULL
)

SELECT * FROM standard
UNION ALL
SELECT * FROM short_leave
UNION ALL
SELECT * FROM lieu_leave
UNION ALL
SELECT * FROM maternity
UNION ALL
SELECT * FROM planner
