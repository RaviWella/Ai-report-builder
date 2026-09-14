-- dim_leave_type — SCD Type 2 leave type dimension (from snap_leave_type).

{{ config(
    materialized='table',
    tags=['leave', 'warehouse_marts'],
) }}

WITH snap AS (
    SELECT
        *,
        dbt_valid_from                                        AS valid_from,
        COALESCE(dbt_valid_to, '9999-12-31 00:00:00+00'::timestamptz)
                                                              AS valid_to,
        (dbt_valid_to IS NULL)                                AS is_current
    FROM {{ ref('snap_leave_type') }}
),

versioned AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY tenant_id, source_system, source_leave_type_id
            ORDER BY valid_from
        )                                                     AS version_number
    FROM snap
)

SELECT
    {{ dbt_utils.generate_surrogate_key([
        'tenant_id', 'source_system', 'source_leave_type_id', 'valid_from'
    ]) }}                                                     AS leave_type_sk,
    tenant_id,
    source_system,
    source_leave_type_id,
    leave_type_code,
    leave_type_name,
    leave_group_name,
    is_paid_leave,
    affects_payroll,
    allow_half_day,
    allow_attachment,
    attachment_mandatory,
    entitlement_based,
    carry_forward_allowed,
    max_carry_forward_days,
    requires_approval,
    requires_coverup,
    leave_category,
    is_active,
    valid_from,
    valid_to,
    is_current,
    version_number,
    _source_updated_at,
    CURRENT_TIMESTAMP                                         AS _loaded_at
FROM versioned
