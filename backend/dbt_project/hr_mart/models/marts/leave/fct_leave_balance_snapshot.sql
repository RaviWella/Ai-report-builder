-- =============================================================================
-- fct_leave_balance_snapshot
-- Periodic leave balance snapshot — employee x leave type x snapshot date.
-- Phase 2: hr_leave_balance (+ prl_leaveentitle when populated).
-- =============================================================================

{{ config(
    materialized='incremental',
    unique_key=[
        'tenant_id', 'source_system', 'balance_source',
        'source_balance_id', 'snapshot_date'
    ],
    incremental_strategy='delete+insert',
    on_schema_change='sync_all_columns',
    tags=['leave', 'warehouse_marts'],
    indexes=[
        {'columns': ['tenant_id', 'snapshot_date_sk'], 'unique': false},
        {'columns': ['tenant_id', 'employee_sk', 'leave_type_sk'], 'unique': false},
    ],
) }}

WITH balances AS (
    SELECT * FROM {{ ref('int_leave_balance_snapshot') }}

    {% if is_incremental() %}
    WHERE _source_updated_at >= (
        SELECT COALESCE(MAX(_source_updated_at), '1970-01-01'::timestamptz) - INTERVAL '1 day'
        FROM {{ this }}
    )
    OR CURRENT_DATE > COALESCE(
        (SELECT MAX(snapshot_date) FROM {{ this }}),
        DATE '1970-01-01'
    )
    {% endif %}
),

balances_norm AS (
    SELECT
        b.*,
        COALESCE(NULLIF(TRIM(b.source_system), ''), '{{ var("source_system") }}')
                                                    AS _source_system_norm,
        CURRENT_DATE                               AS snapshot_date
    FROM balances b
),

employee AS (
    SELECT
        employee_sk,
        tenant_id,
        COALESCE(NULLIF(TRIM(source_system::text), ''), '{{ var("source_system") }}')
                                                    AS source_system_norm,
        source_emp_id,
        valid_from,
        valid_to,
        is_current
    FROM {{ ref('dim_employee') }}
),

leave_type AS (
    SELECT
        leave_type_sk,
        tenant_id,
        COALESCE(NULLIF(TRIM(source_system::text), ''), '{{ var("source_system") }}')
                                                    AS source_system_norm,
        source_leave_type_id,
        leave_type_name,
        valid_from,
        valid_to,
        is_current
    FROM {{ ref('dim_leave_type') }}
),

joined AS (
    SELECT
        b.tenant_id,
        b._source_system_norm                        AS source_system,
        b.balance_source,
        b.source_balance_id,
        b.snapshot_date,
        TO_CHAR(b.snapshot_date, 'YYYYMMDD')::integer AS snapshot_date_sk,

        emp.employee_sk,
        lt.leave_type_sk,

        b.source_emp_id,
        b.source_leave_type_id,
        COALESCE(lt.leave_type_name, b.leave_type_name) AS leave_type_name,

        b.entitled_days,
        b.earned_days,
        b.used_days,
        b.remaining_days,
        b.carry_forward_days,
        b.encashed_days,
        b.expired_days,
        b.pending_approval_days,

        b.entitlement_year,
        b.balance_status,
        b.period_start_date,
        b.period_end_date,
        b.period_end_date                            AS expiry_date,

        b._source_updated_at,
        CURRENT_TIMESTAMP                            AS _loaded_at

    FROM balances_norm b

    LEFT JOIN {{ ref('dim_date') }} dd
        ON dd.calendar_date = b.snapshot_date

    LEFT JOIN LATERAL (
        SELECT e.employee_sk
        FROM employee e
        WHERE TRIM(e.tenant_id::text) = TRIM(b.tenant_id::text)
          AND e.source_system_norm = b._source_system_norm
          AND e.source_emp_id = b.source_emp_id
        ORDER BY
            CASE WHEN e.is_current THEN 0 ELSE 1 END,
            e.valid_from DESC
        LIMIT 1
    ) emp ON TRUE

    LEFT JOIN LATERAL (
        SELECT t.leave_type_sk, t.leave_type_name
        FROM leave_type t
        WHERE TRIM(t.tenant_id::text) = TRIM(b.tenant_id::text)
          AND t.source_system_norm = b._source_system_norm
          AND t.source_leave_type_id = b.source_leave_type_id
        ORDER BY
            CASE WHEN t.is_current THEN 0 ELSE 1 END,
            t.valid_from DESC
        LIMIT 1
    ) lt ON TRUE
),

final AS (
    SELECT
        j.*,
        {{ dbt_utils.generate_surrogate_key([
            'tenant_id', 'source_system', 'balance_source',
            'source_balance_id', 'snapshot_date'
        ]) }}                                        AS balance_snapshot_sk,
        ROW_NUMBER() OVER (
            PARTITION BY
                j.tenant_id, j.source_system, j.balance_source,
                j.source_balance_id, j.snapshot_date
            ORDER BY j.employee_sk NULLS LAST, j._source_updated_at DESC NULLS LAST
        )                                            AS _grain_rn
    FROM joined j
)

SELECT
    balance_snapshot_sk,
    tenant_id,
    source_system,
    balance_source,
    source_balance_id,
    snapshot_date,
    snapshot_date_sk,
    employee_sk,
    leave_type_sk,
    source_emp_id,
    source_leave_type_id,
    leave_type_name,
    entitled_days,
    earned_days,
    used_days,
    remaining_days,
    carry_forward_days,
    encashed_days,
    expired_days,
    pending_approval_days,
    entitlement_year,
    balance_status,
    period_start_date,
    period_end_date,
    expiry_date,
    _source_updated_at,
    _loaded_at
FROM final
WHERE _grain_rn = 1
