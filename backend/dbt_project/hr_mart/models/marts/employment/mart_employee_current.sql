-- =============================================================================
-- mart_employee_current
-- Denormalized current-state OBT for every active employee. This is what
-- BI dashboards' "Employee List" points at.
--
-- Built on dim_employee (is_current rows only) with:
--   - Supervisor name resolved via self-join on dim_employee
--   - age_years and tenure_years computed AT REFRESH TIME (per CLAUDE.md
--     "Things NOT to do" #4 — derived columns based on current_date go in
--     marts, not dim, so they're never stale)
--   - Probation convenience flag and overdue indicator
--   - Tenure bucket for cohort analysis
--
-- Phase 2 covers Employment only. Phase 3+ will extend with LEFT JOINs to
-- monthly attendance + annual leave summaries for MTD/YTD columns.
-- =============================================================================

{{ config(
    materialized='table',
    indexes=[
      {'columns': ['tenant_id', 'legal_entity'], 'unique': false},
      {'columns': ['tenant_id', 'designation'], 'unique': false},
      {'columns': ['tenant_id', 'employment_period'], 'unique': false}
    ]
) }}

WITH current_employees AS (
    SELECT *
    FROM {{ ref('dim_employee') }}
    WHERE is_current = TRUE
      AND emp_status = 'active'
),

supervisor_lookup AS (
    SELECT
        tenant_id,
        source_system,
        emp_no                          AS superior_emp_no,
        emp_fullname                    AS superior_fullname,
        designation_name                AS superior_designation
    FROM {{ ref('dim_employee') }}
    WHERE is_current = TRUE
),

final AS (
    SELECT
        -- ============ KEYS ============
        e.tenant_id,
        e.employee_sk,
        e.source_emp_id,
        e.emp_no,
        e.epf_no,

        -- ============ IDENTITY ============
        e.emp_title,
        e.emp_fullname,
        e.emp_name,
        e.emp_initial,
        e.emp_surname,

        -- ============ DEMOGRAPHICS (with computed age) ============
        e.gender,
        e.date_of_birth,
        CASE
            WHEN e.date_of_birth IS NULL OR e.date_of_birth <= '1900-01-01'::date THEN NULL
            ELSE EXTRACT(YEAR FROM AGE(CURRENT_DATE, e.date_of_birth))::int
        END                                             AS age_years,
        e.civil_status,
        e.nationality_name                              AS nationality,
        e.nic,
        e.passport_no,

        -- ============ CAREER (current state) ============
        e.designation_name                              AS designation,
        e.designation_department,
        e.grade_name                                    AS grade,
        e.employee_category,
        e.employee_category_code,
        e.employment_type,
        e.employment_period,
        e.employee_carder,
        e.employee_carder_label,
        e.legal_entity_name                             AS legal_entity,
        e.legal_entity_code,
        e.location_name,
        e.branch_id,
        e.emp_section_id,
        e.emp_position,
        e.com_hierarchy_level,

        -- ============ SUPERVISOR (resolved) ============
        e.superior_emp_no,
        s.superior_fullname,
        s.superior_designation,

        -- ============ EMPLOYMENT GROUP LINKAGES ============
        e.shift_id,
        e.shift_group_id,
        e.attendance_group_id,
        e.holiday_calendar_id,
        e.leave_group_id,
        e.payroll_group,
        e.cost_center_id,

        -- ============ TENURE ============
        e.join_date,
        CASE
            WHEN e.join_date IS NULL OR e.join_date <= '1900-01-01'::date THEN NULL
            ELSE ROUND(
                EXTRACT(EPOCH FROM AGE(CURRENT_DATE, e.join_date))::numeric
                    / 31536000.0,
                2
            )
        END                                             AS tenure_years,
        CASE
            WHEN e.join_date IS NULL OR e.join_date <= '1900-01-01'::date THEN 'unknown'
            WHEN e.join_date > CURRENT_DATE - INTERVAL '1 year'  THEN '< 1 year'
            WHEN e.join_date > CURRENT_DATE - INTERVAL '3 years' THEN '1-3 years'
            WHEN e.join_date > CURRENT_DATE - INTERVAL '5 years' THEN '3-5 years'
            WHEN e.join_date > CURRENT_DATE - INTERVAL '10 years' THEN '5-10 years'
            ELSE '10+ years'
        END                                             AS tenure_bucket,

        -- ============ PROBATION ============
        e.latest_probation_start_date,
        e.probation_due_date,
        e.probation_completed_date,
        e.probation_status,
        CASE
            WHEN e.probation_status IS NOT NULL
             AND TRIM(e.probation_status::text) = '0'
            THEN TRUE
            ELSE FALSE
        END                                             AS is_on_probation,
        CASE
            WHEN e.probation_status IS NOT NULL
             AND TRIM(e.probation_status::text) = '0'
             AND e.probation_due_date IS NOT NULL
             AND e.probation_due_date > '1900-01-01'::date
             AND e.probation_due_date < CURRENT_DATE
            THEN TRUE
            ELSE FALSE
        END                                             AS is_probation_overdue,

        -- ============ CONTRACT ============
        e.latest_contract_start_date,
        e.employment_due_date,

        -- ============ STATUS ============
        e.emp_status,
        e.emp_lifecycle_status,

        -- ============ SALARY ============
        e.basic_salary,

        -- ============ REFRESH AUDIT ============
        CURRENT_TIMESTAMP                               AS _refreshed_at

    FROM current_employees e
    LEFT JOIN supervisor_lookup s
        ON  s.tenant_id                = e.tenant_id
        AND s.source_system            = e.source_system
        AND s.superior_emp_no          = e.superior_emp_no
)

SELECT * FROM final
