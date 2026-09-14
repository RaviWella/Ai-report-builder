-- vw_turnover — separations from fct_lifecycle_event (hire/exit events).

{{ config(materialized='view') }}

SELECT
    le.source_emp_id                                    AS employee_id,
    d.emp_section_id                                    AS department_id,
    d.branch_id,
    le.event_name                                       AS status,
    CASE
        WHEN le.event_name ILIKE '%resign%' THEN 'resigned'
        WHEN le.event_name ILIKE '%terminat%' THEN 'terminated'
        WHEN le.event_name ILIKE '%retire%' THEN 'retired'
        ELSE 'other'
    END                                                 AS separation_type,
    TO_CHAR(le.effective_date, 'YYYY-MM')               AS period_label,
    EXTRACT(YEAR FROM le.effective_date)::int           AS year
FROM {{ ref('fct_lifecycle_event') }} le
LEFT JOIN {{ ref('dim_employee') }} d
    ON  d.employee_sk = le.employee_sk
    AND d.is_current = TRUE
WHERE le.event_category = 'separation'
  AND le.source_emp_id IS NOT NULL
