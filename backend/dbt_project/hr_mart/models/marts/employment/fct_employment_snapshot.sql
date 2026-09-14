-- =============================================================================
-- fct_employment_snapshot
-- One row per (employee_sk, snapshot_month): employment state at month-end.
-- Strict dimensional FKs: employee_sk → dim_employee, designation_sk →
-- dim_designation (PIT month-end), org_unit_sk → dim_org_unit (current node).
-- Rebuilt as a table each run (month × employee cardinality is manageable for
-- Phase 2 UAT volumes; switch to incremental + partitions when needed).
-- =============================================================================

{{ config(
    materialized='table',
    tags=['warehouse', 'warehouse_marts'],
    indexes=[
        {'columns': ['tenant_id', 'employee_sk', 'snapshot_month'], 'unique': true},
        {'columns': ['tenant_id', 'snapshot_month'], 'unique': false},
        {'columns': ['tenant_id', 'designation_sk'], 'unique': false},
        {'columns': ['tenant_id', 'org_unit_sk'], 'unique': false}
    ]
) }}

WITH month_spine AS (
    SELECT
        gs::date                                          AS snapshot_month,
        (gs::date + INTERVAL '1 month - 1 day')::date     AS month_end_date,
        (
            (gs::date + INTERVAL '1 month - 1 day')::timestamp + INTERVAL '12 hours'
        )::timestamptz                                    AS pit_ts
    FROM generate_series(
        COALESCE(
            (
                SELECT DATE_TRUNC('month', MIN(de.join_date::date))::date
                FROM {{ ref('dim_employee') }} de
                WHERE de.join_date IS NOT NULL
                  AND de.join_date > '1900-01-01'::date
            ),
            DATE_TRUNC('month', CURRENT_DATE)::date
        ),
        DATE_TRUNC('month', CURRENT_DATE)::date,
        INTERVAL '1 month'
    ) AS gs
),

pit_rows AS (
    SELECT
        m.snapshot_month,
        m.month_end_date,
        m.pit_ts,
        de.employee_sk,
        de.tenant_id,
        de.source_system,
        de.source_emp_id,
        de.join_date,
        de.emp_status,
        de.employment_type,
        de.employee_category,
        de.employee_carder,
        de.employee_carder_label,
        de.legal_entity_id,
        de.basic_salary,
        de.probation_status,
        de._source_updated_at,
        de.source_desig_id,
        de.com_hierarchy_id
    FROM month_spine m
    INNER JOIN {{ ref('dim_employee') }} de
        ON m.pit_ts >= de.valid_from
        AND m.pit_ts < de.valid_to
),

with_dims AS (
    SELECT
        p.*,
        dd.designation_sk,
        ou.org_unit_sk
    FROM pit_rows p
    LEFT JOIN {{ ref('dim_designation') }} dd
        ON dd.tenant_id = p.tenant_id
        AND dd.source_system = p.source_system
        AND dd.source_desig_id = p.source_desig_id
        AND p.pit_ts >= dd.valid_from
        AND p.pit_ts < dd.valid_to
    LEFT JOIN {{ ref('dim_org_unit') }} ou
        ON ou.tenant_id = p.tenant_id
        AND ou.source_system = p.source_system
        AND ou.source_hierarchy_id = p.com_hierarchy_id
),

with_tenure AS (
    SELECT
        w.*,
        CASE
            WHEN w.join_date IS NULL OR w.join_date <= '1900-01-01'::date THEN NULL::numeric
            ELSE
                EXTRACT(YEAR FROM AGE(w.month_end_date::timestamp, w.join_date::timestamp))::numeric
                + EXTRACT(MONTH FROM AGE(w.month_end_date::timestamp, w.join_date::timestamp))::numeric
                / 12.0
        END AS years_of_service
    FROM with_dims w
),

final AS (
    SELECT
        {{ dbt_utils.generate_surrogate_key([
            'employee_sk', 'snapshot_month'
        ]) }}                                                 AS employment_snapshot_sk,

        employee_sk,
        org_unit_sk,
        designation_sk,
        snapshot_month,
        emp_status,
        employment_type,
        employee_category                                  AS employment_category,
        employee_carder_label                              AS carder,
        legal_entity_id,
        (emp_status = 'active')                            AS is_active,
        (
            TRIM(COALESCE(probation_status::text, '')) = '0'
        )                                                    AS is_on_probation,
        (emp_status IN ('resigned', 'resign', 'terminated')) AS is_resigned,
        basic_salary,
        years_of_service,
        CASE
            WHEN years_of_service IS NULL THEN 'unknown'
            WHEN years_of_service < 1 THEN '<1yr'
            WHEN years_of_service < 3 THEN '1-3yr'
            WHEN years_of_service < 5 THEN '3-5yr'
            WHEN years_of_service < 10 THEN '5-10yr'
            ELSE '10+yr'
        END                                                  AS tenure_band,

        _source_updated_at,
        tenant_id,
        source_system

    FROM with_tenure
)

SELECT * FROM final
