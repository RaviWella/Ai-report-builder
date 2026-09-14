-- vw_headcount — active roster + lifecycle hire events for movement metrics.

{{ config(materialized='view') }}

WITH active_roster AS (
    SELECT
        m.source_emp_id                                 AS employee_id,
        m.emp_section_id                                AS department_id,
        m.branch_id,
        m.emp_status                                    AS employment_status,
        m.employment_type,
        m.gender,
        TO_CHAR(m.join_date, 'YYYY-MM')                 AS join_period_label,
        NULL::varchar(7)                                AS resign_period_label,
        NULL::varchar(7)                                AS terminate_period_label,
        NULL::varchar(7)                                AS separation_period_label,
        'active'                                        AS metric_status,
        TRUE                                            AS is_active,
        TRUE                                            AS is_current
    FROM {{ ref('mart_employee_current') }} m
),

lifecycle_hires AS (
    SELECT
        le.source_emp_id                                AS employee_id,
        d.emp_section_id                                AS department_id,
        d.branch_id,
        COALESCE(d.emp_status, 'active')                AS employment_status,
        d.employment_type,
        d.gender,
        TO_CHAR(le.effective_date, 'YYYY-MM')           AS join_period_label,
        NULL::varchar(7)                                AS resign_period_label,
        NULL::varchar(7)                                AS terminate_period_label,
        NULL::varchar(7)                                AS separation_period_label,
        'new_hire'                                      AS metric_status,
        TRUE                                            AS is_active,
        TRUE                                            AS is_current
    FROM {{ ref('fct_lifecycle_event') }} le
    LEFT JOIN {{ ref('dim_employee') }} d
        ON  d.employee_sk = le.employee_sk
        AND d.is_current = TRUE
    WHERE le.event_category IN ('hire', 'employment')
      AND le.source_emp_id IS NOT NULL
)

SELECT * FROM active_roster
UNION ALL
SELECT * FROM lifecycle_hires
