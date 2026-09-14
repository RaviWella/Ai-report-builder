-- int_org_unit — org hierarchy nodes from stg_departments (company_hierarchy proxy).

{{ config(materialized='view') }}

SELECT
    '{{ target.name }}'::varchar(64)                       AS tenant_id,
    'minthrm'::varchar(32)                                AS source_system,
    d.id                                                  AS source_hierarchy_id,
    d.code                                                AS org_unit_code,
    d.name                                                AS org_unit_name,
    d.parent_id                                           AS parent_hierarchy_id,
    COALESCE(d.updated_at, d.created_at, NOW())           AS _source_updated_at
FROM {{ source('hr_raw', 'stg_departments') }} d
WHERE d.id IS NOT NULL
