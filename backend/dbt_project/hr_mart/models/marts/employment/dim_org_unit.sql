-- dim_org_unit — org hierarchy dimension (current structure; Type 1).

{{ config(materialized='table') }}

SELECT
    {{ dbt_utils.generate_surrogate_key([
        'tenant_id', 'source_system', 'source_hierarchy_id'
    ]) }}                                                     AS org_unit_sk,
    tenant_id,
    source_system,
    source_hierarchy_id,
    org_unit_code,
    org_unit_name,
    org_unit_name                                             AS unit_name,
    parent_hierarchy_id,
  -- Hierarchy roll-up levels (populate when int_org_unit exposes path columns)
    NULL::varchar(255)                                        AS level_2_name,
    NULL::varchar(255)                                        AS level_3_name,
    NULL::varchar(255)                                        AS level_4_name,
    _source_updated_at,
    CURRENT_TIMESTAMP                                         AS _loaded_at
FROM {{ ref('int_org_unit') }}
