-- =============================================================================
-- mart_leave_monthly_summary
-- Executive leave rollup: month x department x leave type.
-- Built from fct_leave_daily (standard daily grain; Phase 4 aggregates).
-- =============================================================================

{{ config(
    materialized='table',
    tags=['leave', 'warehouse_marts'],
    indexes=[
        {'columns': ['tenant_id', 'year_month', 'department_name', 'leave_type_sk'], 'unique': true},
        {'columns': ['tenant_id', 'year', 'month_number'], 'unique': false},
    ],
) }}

WITH daily AS (
    SELECT *
    FROM {{ ref('fct_leave_daily') }}
    WHERE employee_sk IS NOT NULL
),

enriched AS (
    SELECT
        d.tenant_id,
        d.source_system,
        EXTRACT(YEAR FROM d.leave_date)::smallint          AS year,
        EXTRACT(MONTH FROM d.leave_date)::smallint         AS month_number,
        TO_CHAR(d.leave_date, 'YYYY-MM')                   AS year_month,
        e.org_unit_sk,
        COALESCE(NULLIF(TRIM(e.department_name), ''), 'Unknown')
                                                           AS department_name,
        d.leave_type_sk,
        lt.leave_type_name,
        lt.leave_type_code,
        ls.status_code                                     AS leave_status_code,
        d.employee_sk,
        d.leave_day_count,
        d.leave_hours,
        d.unpaid_leave_hours,
        d.is_half_day
    FROM daily d
    INNER JOIN {{ ref('dim_employee') }} e
        ON  e.employee_sk = d.employee_sk
       AND e.is_current = TRUE
    LEFT JOIN {{ ref('dim_leave_type') }} lt
        ON  lt.leave_type_sk = d.leave_type_sk
       AND lt.is_current = TRUE
    LEFT JOIN {{ ref('dim_leave_status') }} ls
        ON ls.leave_status_sk = d.leave_status_sk
),

agg AS (
    SELECT
        tenant_id,
        source_system,
        year,
        month_number,
        year_month,
        org_unit_sk,
        department_name,
        leave_type_sk,
        MAX(leave_type_name)                               AS leave_type_name,
        MAX(leave_type_code)                               AS leave_type_code,

        SUM(leave_day_count)                               AS total_leave_days,
        SUM(leave_hours)                                   AS total_leave_hours,
        SUM(CASE WHEN leave_status_code = 'approved'
            THEN leave_day_count ELSE 0 END)               AS approved_leave_days,
        SUM(CASE WHEN leave_status_code = 'pending'
            THEN leave_day_count ELSE 0 END)               AS pending_leave_days,
        SUM(unpaid_leave_hours)                            AS unpaid_leave_hours,
        COUNT(DISTINCT employee_sk)                        AS employees_on_leave,
        COUNT(DISTINCT CASE WHEN leave_status_code = 'approved'
            THEN employee_sk END)                          AS employees_with_approved_leave,
        SUM(CASE WHEN is_half_day THEN 1 ELSE 0 END)       AS half_day_leave_count,
        COUNT(*)                                           AS leave_daily_row_count
    FROM enriched
    GROUP BY
        tenant_id,
        source_system,
        year,
        month_number,
        year_month,
        org_unit_sk,
        department_name,
        leave_type_sk
)

SELECT
    {{ dbt_utils.generate_surrogate_key([
        'tenant_id', 'year_month', 'department_name', 'leave_type_sk'
    ]) }}                                                  AS leave_monthly_summary_sk,
    tenant_id,
    source_system,
    year,
    month_number,
    year_month,
    org_unit_sk,
    department_name,
    leave_type_sk,
    leave_type_name,
    leave_type_code,
    total_leave_days,
    total_leave_hours,
    approved_leave_days,
    pending_leave_days,
    unpaid_leave_hours,
    employees_on_leave,
    employees_with_approved_leave,
    half_day_leave_count,
    leave_daily_row_count,
    ROUND(
        approved_leave_days::numeric
            / NULLIF(employees_with_approved_leave, 0),
        2
    )                                                      AS avg_approved_days_per_employee,
    CURRENT_TIMESTAMP                                      AS _refreshed_at
FROM agg
