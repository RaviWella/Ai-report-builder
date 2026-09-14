-- int_lifecycle_event_enriched — normalized career events from stg_lifecycle.
-- Maps MintHRM hr_lifecycle (+ position lookup) into the warehouse lifecycle contract.

{{ config(materialized='view') }}

WITH staged AS (
    SELECT
        l.*,
        COALESCE(NULLIF(TRIM(l.position_name), ''), 'Employment Update')
            AS _position_label
    FROM {{ source('hr_raw', 'stg_lifecycle') }} l
    WHERE l.employee_id IS NOT NULL
      AND l.effective_date IS NOT NULL
),

classified AS (
    SELECT
        s.*,
        CASE
            WHEN s.lifecycle_position = 0 THEN 'employment'
            WHEN s._position_label IN ('Join', 'Re-Join') THEN 'hire'
            WHEN s._position_label ILIKE '%confirmation%' THEN 'confirmation'
            WHEN s._position_label IN (
                'Promotion', 'Demotion', 'Re-Designation', 'Re-Grade',
                'Confirmation with Promotion', 'Promotion with cost center'
            ) THEN 'promotion'
            WHEN s._position_label ILIKE '%transfer%'
              OR s._position_label = 'Inter - Department Transfer'
              OR s._position_label = 'Cost Center change' THEN 'transfer'
            WHEN s._position_label IN ('Salary Increment', 'Benefit Revision')
              OR s._position_label ILIKE '%increment%' THEN 'compensation'
            WHEN s._position_label ILIKE '%resign%'
              OR s._position_label ILIKE '%terminat%'
              OR s._position_label ILIKE '%retire%'
              OR s._position_label IN (
                'Discontinue', 'Discontinue - Active',
                'Discontinue - Terminate - Disciplinary',
                'Discontinue - Terminate - Non Disciplinary',
                'Vacate', 'Deceased', 'Redundant', 'Completion of Contract'
              ) THEN 'separation'
            WHEN s._position_label ILIKE '%contract%'
              OR s._position_label ILIKE '%probation%'
              OR s._position_label ILIKE '%casual%'
              OR s._position_label ILIKE '%trainee%'
              OR s._position_label ILIKE '%internship%' THEN 'contract'
            ELSE 'other'
        END AS _event_category
    FROM staged s
)

SELECT
    '{{ target.name }}'::varchar(64)                   AS tenant_id,
    '{{ var("source_system") }}'::varchar(32)           AS source_system,
    c.id                                              AS source_lifecycle_id,
    c.employee_id                                     AS source_emp_id,
    c.lifecycle_position                              AS source_position_id,
    (c.effective_date AT TIME ZONE 'UTC')::date       AS effective_date,
    c._event_category                                 AS event_category,
    c._position_label                                 AS event_name,
    c.previous_designation,
    c.new_designation,
    c.previous_grade,
    c.new_grade,
    c.previous_location,
    c.new_location,
    c.new_legal_entity,
    c.new_company_section,
    c.new_section,
    c.new_salary,
    c.previous_salary,
    c.reason,
    c.triggered_by_emp_id                             AS triggered_by_emp_id,
    COALESCE(
        (c.approval_date AT TIME ZONE 'UTC')::date,
        (c.approved_date_time AT TIME ZONE 'UTC')::date,
        c.resignation_approved_date
    )                                                 AS approved_date,
    c.last_working_date,
    c.parent_lifecycle_id                             AS parent_source_lifecycle_id,
    COALESCE(c.updated_at, c.created_at, NOW())       AS _source_updated_at
FROM classified c
