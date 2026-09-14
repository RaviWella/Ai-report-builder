-- dim_leave_reason — predefined leave purpose lookup (hr_predefine_leave_purpose).

{{ config(
    materialized='table',
    tags=['leave', 'warehouse_marts'],
) }}

WITH staged AS (
    SELECT
        '{{ target.name }}'::varchar(64)                   AS tenant_id,
        '{{ var("source_system") }}'::varchar(32)          AS source_system,
        r.id                                               AS source_reason_id,
        TRIM(r.name)                                       AS reason_name,
        r.legal_entity_id                                  AS source_legal_entity_id
    FROM {{ source('hr_raw', 'stg_leave_reason') }} r
    WHERE r.id IS NOT NULL
      AND NULLIF(TRIM(r.name), '') IS NOT NULL
)

SELECT
    {{ dbt_utils.generate_surrogate_key([
        'tenant_id', 'source_system', 'source_reason_id'
    ]) }}                                                  AS leave_reason_sk,
    tenant_id,
    source_system,
    source_reason_id,
    reason_name,
    source_legal_entity_id,
    CURRENT_TIMESTAMP                                      AS _loaded_at
FROM staged
