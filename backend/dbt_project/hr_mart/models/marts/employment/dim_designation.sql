-- dim_designation — SCD Type 2 job title dimension (from snap_designation).

{{ config(materialized='table') }}

WITH snap AS (
    SELECT
        *,
        dbt_valid_from                                        AS valid_from,
        COALESCE(dbt_valid_to, '9999-12-31 00:00:00+00'::timestamptz)
                                                              AS valid_to,
        (dbt_valid_to IS NULL)                                AS is_current
    FROM {{ ref('snap_designation') }}
),

versioned AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY tenant_id, source_system, source_desig_id
            ORDER BY valid_from
        )                                                     AS version_number
    FROM snap
)

SELECT
    {{ dbt_utils.generate_surrogate_key([
        'tenant_id', 'source_system', 'source_desig_id', 'valid_from'
    ]) }}                                                     AS designation_sk,
    tenant_id,
    source_system,
    source_desig_id,
    designation_code,
    designation_name,
    grade_name,
    department_id,
    valid_from,
    valid_to,
    is_current,
    version_number,
    _source_updated_at,
    CURRENT_TIMESTAMP                                         AS _loaded_at
FROM versioned
