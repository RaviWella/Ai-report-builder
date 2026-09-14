-- int_salary_change_enriched — salary revisions from stg_lifecycle (hr_lifecycle pay-change rows).
-- When previous_basicsalary is absent in source, prior new_salary is inferred via LAG per employee.

{{ config(materialized='view') }}

WITH pay_rows AS (
    SELECT
        l.*,
        COALESCE(NULLIF(TRIM(l.position_name), ''), 'Salary Change') AS _event_name
    FROM {{ source('hr_raw', 'stg_lifecycle') }} l
    WHERE l.employee_id IS NOT NULL
      AND l.effective_date IS NOT NULL
      AND (
          COALESCE(l.new_salary, 0) > 0
          OR COALESCE(l.previous_salary, 0) > 0
          OR l.lifecycle_position IN (10, 1005, 1007, 140)
          OR COALESCE(l.position_name, '') ILIKE '%increment%'
          OR COALESCE(l.position_name, '') ILIKE '%revision%'
      )
      AND COALESCE(l.lifecycle_position, -1) NOT IN (5)
      AND COALESCE(l.position_name, '') NOT ILIKE '%resign%'
      AND COALESCE(l.position_name, '') NOT ILIKE '%terminat%'
),

with_prev AS (
    SELECT
        p.*,
        COALESCE(
            p.previous_salary,
            LAG(p.new_salary) OVER (
                PARTITION BY p.employee_id
                ORDER BY p.effective_date, p.id
            )
        ) AS _previous_salary
    FROM pay_rows p
),

filtered AS (
    SELECT *
    FROM with_prev w
    WHERE COALESCE(w.new_salary, 0) > 0
      AND (
          w._previous_salary IS NULL
          OR w.new_salary IS DISTINCT FROM w._previous_salary
          OR w.lifecycle_position IN (10, 1005, 1007, 140)
          OR w._event_name ILIKE '%increment%'
          OR w._event_name ILIKE '%revision%'
      )
)

SELECT
    '{{ target.name }}'::varchar(64)                   AS tenant_id,
    '{{ var("source_system") }}'::varchar(32)           AS source_system,
    f.id                                              AS source_increment_id,
    f.employee_id                                     AS source_emp_id,
    (f.effective_date AT TIME ZONE 'UTC')::date       AS effective_date,
    CASE
        WHEN f.lifecycle_position = 1
          OR f._event_name IN ('Join', 'Re-Join') THEN 'initial'
        WHEN f._event_name ILIKE '%increment%'
          OR f.lifecycle_position IN (10, 1005) THEN 'increment'
        WHEN f._event_name ILIKE '%revision%'
          OR f._event_name = 'Benefit Revision'
          OR f.lifecycle_position = 1007 THEN 'revision'
        WHEN f.lifecycle_position = 3
          OR f._event_name = 'Promotion' THEN 'promotion'
        WHEN f.lifecycle_position = 140
          OR f._event_name = 'Re-Grade' THEN 'regrade'
        WHEN f._previous_salary IS NOT NULL
         AND f.new_salary > f._previous_salary THEN 'increase'
        WHEN f._previous_salary IS NOT NULL
         AND f.new_salary < f._previous_salary THEN 'decrease'
        ELSE 'adjustment'
    END                                               AS change_type,
    f._previous_salary                                AS previous_salary,
    f.new_salary,
    CASE
        WHEN f._previous_salary IS NOT NULL
        THEN ROUND((f.new_salary - f._previous_salary)::numeric, 2)
    END                                               AS change_amount,
    CASE
        WHEN COALESCE(f._previous_salary, 0) > 0
        THEN ROUND(
            ((f.new_salary - f._previous_salary) / f._previous_salary * 100.0)::numeric,
            2
        )
    END                                               AS change_pct,
    f.new_designation                                 AS designation_at_change,
    f.new_grade                                       AS grade_at_change,
    f.new_legal_entity                                AS legal_entity_at_change,
    f.triggered_by_emp_id                             AS approved_by_emp_id,
    COALESCE(
        (f.approval_date AT TIME ZONE 'UTC')::date,
        (f.approved_date_time AT TIME ZONE 'UTC')::date,
        f.resignation_approved_date
    )                                                 AS approved_date,
    f.reason,
    f._event_name                                     AS event_name,
    COALESCE(f.updated_at, f.created_at, NOW())       AS _source_updated_at
FROM filtered f
