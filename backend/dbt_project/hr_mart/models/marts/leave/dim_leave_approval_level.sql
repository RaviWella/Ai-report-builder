-- dim_leave_approval_level — approval hierarchy lookup.

{{ config(
    materialized='table',
    tags=['leave', 'warehouse_marts'],
) }}

WITH levels AS (
    SELECT *
    FROM (
        VALUES
            (0, 'cover_up', 'Cover Up', 1),
            (1, 'supervisor', 'Supervisor', 2),
            (2, 'supervisor_second', 'Second Supervisor', 3),
            (3, 'supervisor_third', 'Third Supervisor', 4),
            (9, 'hr', 'HR', 5),
            (99, 'final', 'Final Approval', 6)
    ) AS t(level_code, level_key, level_name, display_order)
)

SELECT
    {{ dbt_utils.generate_surrogate_key(['level_key']) }}   AS leave_approval_level_sk,
    level_code,
    level_key,
    level_name,
    display_order,
    CURRENT_TIMESTAMP                                       AS _loaded_at
FROM levels
