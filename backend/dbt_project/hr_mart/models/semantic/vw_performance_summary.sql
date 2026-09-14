-- vw_performance_summary — AI-safe performance review view

{{
  config(materialized='view')
}}

WITH reviews AS (
    SELECT * FROM {{ source('hr_raw', 'stg_performance_reviews') }}
    WHERE status = 'completed'
)

SELECT
    r.employee_id,
    e.department_id,
    e.branch_id,
    r.review_period                                 AS period_label,
    r.review_year,
    r.overall_score,
    r.rating,
    CASE
        WHEN r.rating IN ('excellent', 'outstanding') THEN 'high_performer'
        WHEN r.rating IN ('satisfactory', 'good')    THEN 'meets_expectations'
        ELSE 'needs_improvement'
    END                                             AS status
FROM reviews r
JOIN {{ ref('dim_employee') }} e ON e.employee_id = r.employee_id
