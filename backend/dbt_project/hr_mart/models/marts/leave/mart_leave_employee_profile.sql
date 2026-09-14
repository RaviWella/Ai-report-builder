-- =============================================================================
-- mart_leave_employee_profile
-- Employee leave behavior profile — applications, sick frequency, approval SLA.
-- =============================================================================

{{ config(
    materialized='table',
    tags=['leave', 'warehouse_marts'],
    indexes=[
        {'columns': ['tenant_id', 'employee_sk'], 'unique': true},
    ],
) }}

WITH apps AS (
    SELECT
        a.tenant_id,
        a.source_system,
        a.employee_sk,
        a.leave_source_code,
        a.start_date,
        a.requested_days,
        a.approved_days,
        a.approval_duration_hours,
        a.leave_reason_text,
        ls.status_code,
        lt.leave_type_name,
        lt.leave_type_code
    FROM {{ ref('fct_leave_application') }} a
    LEFT JOIN {{ ref('dim_leave_status') }} ls
        ON ls.leave_status_sk = a.leave_status_sk
    LEFT JOIN {{ ref('dim_leave_type') }} lt
        ON  lt.leave_type_sk = a.leave_type_sk
       AND lt.is_current = TRUE
    WHERE a.employee_sk IS NOT NULL
),

app_profile AS (
    SELECT
        tenant_id,
        source_system,
        employee_sk,

        COUNT(*)                                           AS total_applications,
        COUNT(*) FILTER (WHERE status_code = 'approved')   AS approved_applications,
        COUNT(*) FILTER (WHERE status_code = 'rejected')     AS rejected_applications,
        COUNT(*) FILTER (WHERE status_code = 'cancelled')    AS cancelled_applications,
        COUNT(*) FILTER (WHERE status_code = 'pending')      AS pending_applications,

        SUM(requested_days)                                AS total_requested_days,
        SUM(CASE WHEN status_code = 'approved'
            THEN approved_days ELSE 0 END)                 AS total_approved_days,
        SUM(CASE WHEN status_code = 'approved'
             AND EXTRACT(YEAR FROM start_date) = EXTRACT(YEAR FROM CURRENT_DATE)
            THEN approved_days ELSE 0 END)                 AS ytd_approved_days,

        ROUND(AVG(approval_duration_hours) FILTER (
            WHERE approval_duration_hours IS NOT NULL
        ), 2)                                              AS avg_approval_duration_hours,

        SUM(CASE
            WHEN status_code = 'approved'
             AND (
                LOWER(COALESCE(leave_type_name, '')) LIKE '%sick%'
                OR LOWER(COALESCE(leave_type_code, '')) LIKE '%sick%'
                OR LOWER(COALESCE(leave_reason_text, '')) LIKE '%sick%'
             )
            THEN approved_days
            ELSE 0
        END)                                               AS sick_leave_days,

        COUNT(*) FILTER (WHERE leave_source_code = 'SHORT')
                                                           AS short_leave_applications,
        MAX(start_date)                                    AS last_leave_start_date,
        MIN(start_date)                                    AS first_leave_start_date
    FROM apps
    GROUP BY tenant_id, source_system, employee_sk
),

short_profile AS (
    SELECT
        tenant_id,
        employee_sk,
        COUNT(*)                                           AS short_leave_count,
        SUM(deducted_leave_days)                           AS short_leave_deducted_days,
        SUM(short_leave_hours)                             AS short_leave_hours_total
    FROM {{ ref('fct_short_leave_usage') }}
    WHERE employee_sk IS NOT NULL
    GROUP BY tenant_id, employee_sk
),

final AS (
    SELECT
        p.tenant_id,
        p.source_system,
        p.employee_sk,

        e.emp_no,
        e.emp_fullname,
        e.department_name,
        e.designation_name                                 AS designation,
        e.legal_entity_name                                AS legal_entity,

        p.total_applications,
        p.approved_applications,
        p.rejected_applications,
        p.cancelled_applications,
        p.pending_applications,
        p.total_requested_days,
        p.total_approved_days,
        p.ytd_approved_days,
        p.avg_approval_duration_hours,
        p.sick_leave_days,
        COALESCE(s.short_leave_count, p.short_leave_applications, 0)
                                                           AS short_leave_count,
        COALESCE(s.short_leave_deducted_days, 0)           AS short_leave_deducted_days,
        COALESCE(s.short_leave_hours_total, 0)             AS short_leave_hours_total,
        p.last_leave_start_date,
        p.first_leave_start_date,

        ROUND(
            p.sick_leave_days::numeric
                / NULLIF(p.total_approved_days, 0) * 100,
            2
        )                                                  AS sick_leave_ratio_pct,

        CURRENT_TIMESTAMP                                  AS _refreshed_at

    FROM app_profile p
    INNER JOIN {{ ref('dim_employee') }} e
        ON  e.employee_sk = p.employee_sk
       AND e.is_current = TRUE
    LEFT JOIN short_profile s
        ON  s.tenant_id = p.tenant_id
       AND s.employee_sk = p.employee_sk
)

SELECT * FROM final
