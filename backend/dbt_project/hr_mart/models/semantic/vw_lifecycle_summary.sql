-- vw_lifecycle_summary — lifecycle events by category × month.

{{ config(materialized='view') }}

SELECT
    le.tenant_id,
    le.source_system,
    TO_CHAR(le.effective_date, 'YYYY-MM')               AS period_label,
    le.event_category,
    le.event_name,
    le.source_emp_id                                    AS employee_id,
    d.emp_section_id                                    AS department_id,
    d.branch_id,
    le.effective_date,
    le.new_salary,
    le.previous_salary
FROM {{ ref('fct_lifecycle_event') }} le
LEFT JOIN {{ ref('dim_employee') }} d
    ON  d.employee_sk = le.employee_sk
    AND d.is_current = TRUE
