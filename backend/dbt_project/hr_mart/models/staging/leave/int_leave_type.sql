-- int_leave_type — snapshot-ready leave type row from stg_leave_types.

{{ config(materialized='view') }}

WITH staged AS (
    SELECT
        '{{ target.name }}'::varchar(64)                   AS tenant_id,
        '{{ var("source_system") }}'::varchar(32)          AS source_system,
        t.id                                               AS source_leave_type_id,
        t.code                                             AS leave_type_code,
        t.name                                             AS leave_type_name,
        NULL::varchar(128)                                 AS leave_group_name,
        COALESCE(t.is_paid, TRUE)                          AS is_paid_leave,
        COALESCE(NOT t.is_paid, FALSE)                     AS affects_payroll,
        COALESCE(t.allow_half_day, FALSE)                  AS allow_half_day,
        COALESCE(t.allow_attachment, FALSE)                AS allow_attachment,
        COALESCE(t.attachment_mandatory, FALSE)            AS attachment_mandatory,
        COALESCE(t.entitlement_based, FALSE)               AS entitlement_based,
        COALESCE(t.carry_forward, FALSE)                   AS carry_forward_allowed,
        NULL::numeric(8, 2)                                AS max_carry_forward_days,
        COALESCE(t.requires_approval, FALSE)               AS requires_approval,
        COALESCE(t.requires_coverup, FALSE)                AS requires_coverup,
        'STANDARD'::varchar(32)                            AS leave_category,
        COALESCE(t.is_active, TRUE)                        AS is_active,
        COALESCE(t.updated_at, t.created_at, NOW())        AS _source_updated_at
    FROM {{ source('hr_raw', 'stg_leave_types') }} t
    WHERE t.id IS NOT NULL
)

SELECT
    {{ dbt_utils.generate_surrogate_key(['tenant_id', 'source_system', 'source_leave_type_id']) }}
                                                      AS leave_type_nk,
    *
FROM staged
