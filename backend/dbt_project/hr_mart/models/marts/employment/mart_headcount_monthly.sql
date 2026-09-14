-- =============================================================================
-- mart_headcount_monthly
-- Monthly workforce summary (Mart Layer Design §5 — mart_headcount_monthly).
--
-- Grain: one row per (tenant_id, source_system, snapshot_month).
-- Built from fct_employment_snapshot (month-end PIT state). Metrics are
-- month-end headcounts, not lifecycle "events within the month" (that needs
-- fct_lifecycle_event or SCD2 transition logic in a later phase).
-- =============================================================================

{{ config(
    materialized='table',
    tags=['warehouse', 'warehouse_marts'],
    indexes=[
        {'columns': ['tenant_id', 'source_system', 'snapshot_month'], 'unique': true},
        {'columns': ['tenant_id', 'snapshot_month'], 'unique': false},
        {'columns': ['snapshot_month_sk'], 'unique': false}
    ]
) }}

WITH monthly_agg AS (
    SELECT
        f.tenant_id,
        f.source_system,
        f.snapshot_month,

        COUNT(*) FILTER (WHERE f.is_active)
            AS active_headcount,

        COUNT(*) FILTER (WHERE f.is_resigned)
            AS resigned_headcount_eom,

        COUNT(*) FILTER (
            WHERE f.emp_status IN (
                'terminate', 'terminate_d', 'terminate_n', 'terminated'
            )
        ) AS terminated_headcount_eom,

        COUNT(*) FILTER (
            WHERE NOT f.is_active
              AND NOT f.is_resigned
              AND f.emp_status NOT IN (
                  'terminate', 'terminate_d', 'terminate_n', 'terminated'
              )
        ) AS other_non_active_headcount_eom,

        SUM(CASE WHEN f.is_active THEN COALESCE(f.basic_salary, 0) ELSE 0 END)
            AS monthly_salary_cost_active,

        AVG(CASE WHEN f.is_active THEN f.years_of_service END)
            AS avg_years_of_service_active,

        MAX(f._source_updated_at) AS _source_updated_at
    FROM {{ ref('fct_employment_snapshot') }} f
    GROUP BY f.tenant_id, f.source_system, f.snapshot_month
),

with_date_dim AS (
    SELECT
        m.*,
        d.date_sk AS snapshot_month_sk
    FROM monthly_agg m
    LEFT JOIN {{ ref('dim_date') }} d
        ON d.calendar_date = m.snapshot_month
),

with_mom AS (
    SELECT
        w.*,
        LAG(w.active_headcount) OVER (
            PARTITION BY w.tenant_id, w.source_system
            ORDER BY w.snapshot_month
        ) AS prior_month_active_headcount,
        w.active_headcount - LAG(w.active_headcount) OVER (
            PARTITION BY w.tenant_id, w.source_system
            ORDER BY w.snapshot_month
        ) AS net_active_headcount_change_mom
    FROM with_date_dim w
)

SELECT
    {{ dbt_utils.generate_surrogate_key([
        'tenant_id', 'source_system', 'snapshot_month'
    ]) }}                         AS headcount_monthly_sk,

    tenant_id,
    source_system,
    snapshot_month,
    snapshot_month_sk,

    active_headcount,
    resigned_headcount_eom,
    terminated_headcount_eom,
    other_non_active_headcount_eom,

    prior_month_active_headcount,
    net_active_headcount_change_mom,

    monthly_salary_cost_active,
    avg_years_of_service_active,

    active_headcount::numeric      AS fte_equivalent,

    CURRENT_TIMESTAMP              AS _refreshed_at,
    _source_updated_at

FROM with_mom
