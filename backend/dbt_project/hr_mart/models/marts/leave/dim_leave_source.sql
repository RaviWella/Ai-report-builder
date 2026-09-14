-- dim_leave_source — leave module origin lookup (Phase 1: standard leave only).

{{ config(
    materialized='table',
    tags=['leave', 'warehouse_marts'],
) }}

WITH sources AS (
    SELECT *
    FROM (
        VALUES
            ('STANDARD', 'Standard Leave', 1),
            ('SHORT', 'Short Leave', 2),
            ('LIEU', 'Lieu Leave', 3),
            ('MATERNITY', 'Maternity Leave', 4),
            ('EDUCATIONAL', 'Educational Leave', 5),
            ('DAY_OFF', 'Day Off', 6),
            ('PLANNER', 'Leave Planner', 7)
    ) AS t(source_code, source_name, display_order)
)

SELECT
    {{ dbt_utils.generate_surrogate_key(['source_code']) }}     AS leave_source_sk,
    source_code,
    source_name,
    display_order,
    (source_code IN ('STANDARD', 'SHORT', 'LIEU', 'MATERNITY', 'PLANNER')) AS is_implemented,
    CURRENT_TIMESTAMP                                         AS _loaded_at
FROM sources
