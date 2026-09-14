-- =============================================================================
-- mart_department_leave_heatmap
-- Department x calendar date occupancy for heatmap / absence planning.
-- =============================================================================

{{ config(
    materialized='table',
    tags=['leave', 'warehouse_marts'],
    indexes=[
        {'columns': ['tenant_id', 'calendar_date', 'department_name'], 'unique': true},
        {'columns': ['tenant_id', 'calendar_date'], 'unique': false},
    ],
) }}

WITH daily AS (
    SELECT
        d.tenant_id,
        d.source_system,
        d.leave_date                                       AS calendar_date,
        d.employee_sk,
        d.leave_day_count,
        ls.status_code,
        e.org_unit_sk,
        COALESCE(NULLIF(TRIM(e.department_name), ''), 'Unknown')
                                                           AS department_name
    FROM {{ ref('fct_leave_daily') }} d
    INNER JOIN {{ ref('dim_employee') }} e
        ON  e.employee_sk = d.employee_sk
       AND e.is_current = TRUE
    LEFT JOIN {{ ref('dim_leave_status') }} ls
        ON ls.leave_status_sk = d.leave_status_sk
    WHERE d.employee_sk IS NOT NULL
),

dept_headcount AS (
    SELECT
        tenant_id,
        org_unit_sk,
        COALESCE(NULLIF(TRIM(department_name), ''), 'Unknown')
                                                           AS department_name,
        COUNT(*)                                           AS department_headcount
    FROM {{ ref('dim_employee') }}
    WHERE is_current = TRUE
      AND emp_status = 'active'
    GROUP BY tenant_id, org_unit_sk, department_name
),

agg AS (
    SELECT
        d.tenant_id,
        d.source_system,
        d.calendar_date,
        d.org_unit_sk,
        d.department_name,

        COUNT(DISTINCT CASE WHEN d.status_code = 'approved'
            THEN d.employee_sk END)                        AS employees_on_leave,
        SUM(CASE WHEN d.status_code = 'approved'
            THEN d.leave_day_count ELSE 0 END)             AS approved_leave_days,
        SUM(CASE WHEN d.status_code = 'pending'
            THEN d.leave_day_count ELSE 0 END)             AS pending_leave_days,
        COUNT(DISTINCT d.employee_sk)                      AS employees_with_any_leave_status
    FROM daily d
    GROUP BY
        d.tenant_id,
        d.source_system,
        d.calendar_date,
        d.org_unit_sk,
        d.department_name
),

final AS (
    SELECT
        a.tenant_id,
        a.source_system,
        a.calendar_date,
        a.org_unit_sk,
        a.department_name,
        a.employees_on_leave,
        a.approved_leave_days,
        a.pending_leave_days,
        a.employees_with_any_leave_status,
        COALESCE(h.department_headcount, 0)                    AS department_headcount,
        ROUND(
            a.employees_on_leave::numeric
                / NULLIF(h.department_headcount, 0) * 100,
            2
        )                                                      AS absence_rate_pct
    FROM agg a
    LEFT JOIN dept_headcount h
        ON  h.tenant_id = a.tenant_id
       AND h.org_unit_sk IS NOT DISTINCT FROM a.org_unit_sk
       AND h.department_name = a.department_name
)

SELECT
    {{ dbt_utils.generate_surrogate_key([
        'tenant_id', 'calendar_date', 'department_name'
    ]) }}                                                  AS department_leave_heatmap_sk,
    tenant_id,
    source_system,
    calendar_date,
    TO_CHAR(calendar_date, 'YYYYMMDD')::integer            AS calendar_date_sk,
    org_unit_sk,
    department_name,
    employees_on_leave,
    approved_leave_days,
    pending_leave_days,
    employees_with_any_leave_status,
    department_headcount,
    absence_rate_pct,
    CURRENT_TIMESTAMP                                      AS _refreshed_at
FROM final
