-- =============================================================================
-- fct_overtime
-- Payroll overtime fact per employee × day (Phase 2: derived from daily attendance
-- until prl_overtime is staged). Replace with int_overtime_processed when available.
-- =============================================================================

{{ config(
    materialized='table',
    tags=['warehouse', 'warehouse_marts'],
    indexes=[
        {'columns': ['tenant_id', 'source_system', 'source_ot_id'], 'unique': true},
        {'columns': ['tenant_id', 'employee_sk', 'ot_date'], 'unique': false},
    ]
) }}

SELECT
    a.tenant_id,
    a.source_system,
    a.source_atten_id                               AS source_ot_id,
    e.source_emp_id,
    a.employee_sk,
    a.shift_day                                     AS ot_date,
    COALESCE(a.overtime_hours, 0)::numeric(10, 2)   AS total_ot_hours,
    a._source_updated_at,
    CURRENT_TIMESTAMP                               AS _loaded_at
FROM {{ ref('fct_daily_attendance') }} a
INNER JOIN {{ ref('dim_employee') }} e
    ON e.employee_sk = a.employee_sk
   AND e.tenant_id = a.tenant_id
WHERE COALESCE(a.overtime_seconds, 0) > 0
   OR a.has_overtime = TRUE
