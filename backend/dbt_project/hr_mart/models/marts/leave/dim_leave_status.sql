-- dim_leave_status — normalized leave workflow status lookup.

{{ config(
    materialized='table',
    tags=['leave', 'warehouse_marts'],
) }}

WITH statuses AS (
    SELECT *
    FROM (
        VALUES
            ('pending', 'Pending', 0),
            ('approved', 'Approved', 1),
            ('rejected', 'Rejected', 2),
            ('cancelled', 'Cancelled', 3),
            ('unknown', 'Unknown', -1),
            ('hr_approved', 'HR Approved', 10),
            ('coverup_pending', 'Cover-Up Pending', 11),
            ('superior_pending', 'Superior Pending', 12),
            ('auto_approved', 'Auto Approved', 13)
    ) AS t(status_code, status_name, source_status_id)
)

SELECT
    {{ dbt_utils.generate_surrogate_key(['status_code']) }}   AS leave_status_sk,
    status_code,
    status_name,
    source_status_id,
    CURRENT_TIMESTAMP                                         AS _loaded_at
FROM statuses
