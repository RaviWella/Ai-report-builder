-- =============================================================================
-- fct_leave_application
-- Central leave transaction fact — unified modules (standard, short, lieu, maternity, planner).
-- Grain: one row per leave application.
-- =============================================================================

{{ config(
    materialized='incremental',
    unique_key=['tenant_id', 'source_system', 'source_application_id', 'leave_source_code'],
    incremental_strategy='delete+insert',
    on_schema_change='sync_all_columns',
    tags=['leave', 'warehouse_marts'],
    indexes=[
        {'columns': ['tenant_id', 'employee_sk', 'start_date'], 'unique': false},
        {'columns': ['tenant_id', 'leave_type_sk'], 'unique': false},
        {'columns': ['tenant_id', 'leave_status_sk'], 'unique': false},
        {'columns': ['tenant_id', 'start_date_sk'], 'unique': false},
    ],
) }}

WITH apps AS (
    SELECT * FROM {{ ref('int_leave_application') }}

    {% if is_incremental() %}
    WHERE _source_updated_at >= (
        SELECT COALESCE(MAX(_source_updated_at), '1970-01-01'::timestamptz) - INTERVAL '1 hour'
        FROM {{ this }}
    )
    {% endif %}
),

apps_norm AS (
    SELECT
        a.*,
        COALESCE(NULLIF(TRIM(a.source_system), ''), '{{ var("source_system") }}')
                                                    AS _source_system_norm
    FROM apps a
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
        is_paid_leave,
        valid_from,
        valid_to,
        is_current
    FROM {{ ref('dim_leave_type') }}
),

leave_status AS (
    SELECT leave_status_sk, status_code
    FROM {{ ref('dim_leave_status') }}
),

leave_source AS (
    SELECT leave_source_sk, source_code
    FROM {{ ref('dim_leave_source') }}
),

leave_reason AS (
    SELECT
        leave_reason_sk,
        tenant_id,
        source_system,
        source_reason_id
    FROM {{ ref('dim_leave_reason') }}
),

joined AS (
    SELECT
        a.tenant_id,
        a._source_system_norm                        AS source_system,
        a.source_application_id,
        a.leave_source_code,

        emp.employee_sk,
        lt.leave_type_sk,
        ls.leave_status_sk,
        src.leave_source_sk,
        lr.leave_reason_sk,

        TO_CHAR(a.start_date, 'YYYYMMDD')::integer  AS start_date_sk,
        TO_CHAR(a.end_date, 'YYYYMMDD')::integer    AS end_date_sk,
        TO_CHAR(a.request_date::date, 'YYYYMMDD')::integer
                                                    AS request_date_sk,
        TO_CHAR(a.approval_date::date, 'YYYYMMDD')::integer
                                                    AS approval_date_sk,

        a.source_emp_id,
        a.source_leave_type_id,
        a.leave_status_code,
        a.source_status_code,
        a.source_final_status_code,
        a.source_purpose_id,
        a.source_approved_by,

        a.start_date,
        a.end_date,
        a.request_date,
        a.approval_date,

        a.requested_days,
        a.approved_days,
        CASE
            WHEN COALESCE(lt.is_paid_leave, TRUE) = FALSE
             AND a.leave_status_code = 'approved'
            THEN a.approved_days
            ELSE 0::numeric(8, 2)
        END                                          AS unpaid_days,
        CASE
            WHEN a.leave_status_code = 'rejected' THEN a.requested_days
            ELSE 0::numeric(8, 2)
        END                                          AS rejected_days,
        CASE
            WHEN a.leave_status_code = 'cancelled' THEN a.requested_days
            ELSE 0::numeric(8, 2)
        END                                          AS cancelled_days,

        a.leave_reason_text,
        a.is_hr_approval,
        (a.leave_status_code = 'cancelled')          AS cancelled_flag,
        FALSE                                        AS emergency_leave_flag,
        FALSE                                        AS attachment_submitted_flag,
        (COALESCE(lt.is_paid_leave, TRUE) = FALSE)   AS payroll_impacted_flag,
        FALSE                                        AS is_planned_leave,

        CASE
            WHEN a.request_date IS NOT NULL AND a.approval_date IS NOT NULL
            THEN EXTRACT(EPOCH FROM (a.approval_date - a.request_date)) / 3600.0
            ELSE NULL
        END::numeric(10, 2)                          AS approval_duration_hours,

        a.source_created_at                            AS created_timestamp,
        a.source_updated_at                            AS updated_timestamp,
        a._source_updated_at,
        CURRENT_TIMESTAMP                            AS _loaded_at

    FROM apps_norm a

    LEFT JOIN LATERAL (
        SELECT e.employee_sk
        FROM employee e
        WHERE TRIM(e.tenant_id::text) = TRIM(a.tenant_id::text)
          AND e.source_system_norm = a._source_system_norm
          AND e.source_emp_id = a.source_emp_id
        ORDER BY
            CASE
                WHEN a.start_date >= ((e.valid_from AT TIME ZONE 'UTC'))::date
                 AND a.start_date < ((e.valid_to AT TIME ZONE 'UTC'))::date
                THEN 0 ELSE 1
            END,
            CASE WHEN e.is_current THEN 0 ELSE 1 END,
            e.valid_from DESC
        LIMIT 1
    ) emp ON TRUE

    LEFT JOIN LATERAL (
        SELECT t.leave_type_sk, t.is_paid_leave
        FROM leave_type t
        WHERE TRIM(t.tenant_id::text) = TRIM(a.tenant_id::text)
          AND t.source_system_norm = a._source_system_norm
          AND t.source_leave_type_id = a.source_leave_type_id
        ORDER BY
            CASE
                WHEN a.start_date >= ((t.valid_from AT TIME ZONE 'UTC'))::date
                 AND a.start_date < ((t.valid_to AT TIME ZONE 'UTC'))::date
                THEN 0 ELSE 1
            END,
            CASE WHEN t.is_current THEN 0 ELSE 1 END,
            t.valid_from DESC
        LIMIT 1
    ) lt ON TRUE

    LEFT JOIN leave_status ls
        ON ls.status_code = a.leave_status_code

    LEFT JOIN leave_source src
        ON src.source_code = a.leave_source_code

    LEFT JOIN leave_reason lr
        ON TRIM(lr.tenant_id::text) = TRIM(a.tenant_id::text)
       AND lr.source_system = a._source_system_norm
       AND lr.source_reason_id = a.source_purpose_id
       AND a.source_purpose_id IS NOT NULL
),

final AS (
    SELECT
        j.*,
        {{ dbt_utils.generate_surrogate_key([
            'tenant_id', 'source_system', 'source_application_id', 'leave_source_code'
        ]) }}                                        AS leave_application_sk,
        ROW_NUMBER() OVER (
            PARTITION BY j.tenant_id, j.source_system, j.source_application_id, j.leave_source_code
            ORDER BY j.employee_sk NULLS LAST, j._source_updated_at DESC NULLS LAST
        )                                            AS _grain_rn
    FROM joined j
)

SELECT
    leave_application_sk,
    tenant_id,
    source_system,
    source_application_id,
    leave_source_code,
    employee_sk,
    leave_type_sk,
    leave_status_sk,
    leave_source_sk,
    leave_reason_sk,
    request_date_sk,
    start_date_sk,
    end_date_sk,
    approval_date_sk,
    source_emp_id,
    source_leave_type_id,
    leave_status_code,
    source_status_code,
    source_final_status_code,
    source_purpose_id,
    source_approved_by,
    start_date,
    end_date,
    request_date,
    approval_date,
    requested_days,
    approved_days,
    unpaid_days,
    rejected_days,
    cancelled_days,
    leave_reason_text,
    is_hr_approval,
    cancelled_flag,
    emergency_leave_flag,
    attachment_submitted_flag,
    payroll_impacted_flag,
    is_planned_leave,
    approval_duration_hours,
    created_timestamp,
    updated_timestamp,
    _source_updated_at,
    _loaded_at
FROM final
WHERE _grain_rn = 1
