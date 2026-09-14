-- int_designation — snapshot-ready designation row from stg_designations.

{{ config(materialized='view') }}

WITH staged AS (
    SELECT
        '{{ target.name }}'::varchar(64)                   AS tenant_id,
        'minthrm'::varchar(32)                            AS source_system,
        d.id                                              AS source_desig_id,
        d.code                                            AS designation_code,
        d.title                                           AS designation_name,
        d.grade                                           AS grade_name,
        d.department_id                                   AS department_id,
        COALESCE(d.updated_at, d.created_at, NOW())       AS _source_updated_at
    FROM {{ source('hr_raw', 'stg_designations') }} d
    WHERE d.id IS NOT NULL
)

SELECT
    {{ dbt_utils.generate_surrogate_key(['tenant_id', 'source_system', 'source_desig_id']) }}
                                                      AS designation_nk,
    *
FROM staged
