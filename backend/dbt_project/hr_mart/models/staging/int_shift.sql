-- int_shift — distinct shift definitions observed in attendance staging.

{{ config(materialized='view') }}

WITH distinct_shifts AS (
    SELECT DISTINCT
        a.shift_id                                      AS source_shift_id
    FROM {{ source('hr_raw', 'stg_attendance') }} a
    WHERE a.shift_id IS NOT NULL
),

staged AS (
    SELECT
        '{{ target.name }}'::varchar(64)                   AS tenant_id,
        '{{ var("source_system") }}'::varchar(32)         AS source_system,
        s.source_shift_id,
        ('Shift ' || s.source_shift_id::text)             AS shift_name,
        NOW()                                             AS _source_updated_at
    FROM distinct_shifts s
)

SELECT
    {{ dbt_utils.generate_surrogate_key(['tenant_id', 'source_system', 'source_shift_id']) }}
                                                      AS shift_nk,
    *
FROM staged
