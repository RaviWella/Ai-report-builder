-- =============================================================================
-- fct_leave_approval
-- One row per approval action (Phase 2: standard leave superiors).
-- =============================================================================

{{ config(
    materialized='incremental',
    unique_key=['tenant_id', 'source_system', 'source_approval_id'],
    incremental_strategy='delete+insert',
    on_schema_change='sync_all_columns',
    tags=['leave', 'warehouse_marts'],
    indexes=[
        {'columns': ['tenant_id', 'leave_application_sk'], 'unique': false},
        {'columns': ['tenant_id', 'approver_employee_sk'], 'unique': false},
        {'columns': ['tenant_id', 'approval_status_code'], 'unique': false},
    ],
) }}

WITH approvals AS (
    SELECT * FROM {{ ref('int_leave_approval') }}

    {% if is_incremental() %}
    WHERE _source_updated_at >= (
        SELECT COALESCE(MAX(_source_updated_at), '1970-01-01'::timestamptz) - INTERVAL '1 hour'
        FROM {{ this }}
    )
    {% endif %}
),

approvals_norm AS (
    SELECT
        a.*,
        COALESCE(NULLIF(TRIM(a.source_system), ''), '{{ var("source_system") }}')
                                                    AS _source_system_norm
    FROM approvals a
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

approval_level AS (
    SELECT leave_approval_level_sk, level_code, level_name
    FROM {{ ref('dim_leave_approval_level') }}
),

leave_status AS (
    SELECT leave_status_sk, status_code
    FROM {{ ref('dim_leave_status') }}
),

applications AS (
    SELECT
        leave_application_sk,
        tenant_id,
        source_system,
        source_application_id,
        leave_source_code,
        employee_sk,
        start_date,
        end_date,
        leave_status_code
    FROM {{ ref('fct_leave_application') }}
),

joined AS (
    SELECT
        a.tenant_id,
        a._source_system_norm                        AS source_system,
        a.source_approval_id,
        a.source_application_id,
        a.leave_source_code,

        app.leave_application_sk,
        app.employee_sk                              AS applicant_employee_sk,
        approver.employee_sk                         AS approver_employee_sk,
        lvl.leave_approval_level_sk,
        ls.leave_status_sk                           AS approval_status_sk,

        TO_CHAR(COALESCE(a.action_timestamp::date, CURRENT_DATE), 'YYYYMMDD')::integer
                                                    AS action_date_sk,
        COALESCE(a.action_timestamp::date, CURRENT_DATE) AS action_date,

        a.source_approver_emp_id,
        a.approval_level_code,
        lvl.level_name                               AS approval_level_name,
        a.approval_status_code,
        a.application_status_code,

        ROW_NUMBER() OVER (
            PARTITION BY a.source_application_id, a.approval_level_code
            ORDER BY a.source_approval_id
        )                                            AS approval_sequence,

        NULL::text                                   AS approval_comment,
        (a.approval_status_code = 'approved')        AS is_final_approval,

        a.source_created_at                            AS created_timestamp,
        a.source_updated_at                            AS updated_timestamp,
        a._source_updated_at,
        CURRENT_TIMESTAMP                            AS _loaded_at

    FROM approvals_norm a

    LEFT JOIN applications app
        ON TRIM(app.tenant_id::text) = TRIM(a.tenant_id::text)
       AND app.source_system = a._source_system_norm
       AND app.source_application_id = a.source_application_id
       AND app.leave_source_code = a.leave_source_code

    LEFT JOIN LATERAL (
        SELECT e.employee_sk
        FROM employee e
        WHERE TRIM(e.tenant_id::text) = TRIM(a.tenant_id::text)
          AND e.source_system_norm = a._source_system_norm
          AND e.source_emp_id = a.source_approver_emp_id
        ORDER BY
            CASE WHEN e.is_current THEN 0 ELSE 1 END,
            e.valid_from DESC
        LIMIT 1
    ) approver ON TRUE

    LEFT JOIN approval_level lvl
        ON lvl.level_code = a.approval_level_code

    LEFT JOIN leave_status ls
        ON ls.status_code = a.approval_status_code
),

final AS (
    SELECT
        j.*,
        {{ dbt_utils.generate_surrogate_key([
            'tenant_id', 'source_system', 'source_approval_id'
        ]) }}                                        AS leave_approval_sk,
        ROW_NUMBER() OVER (
            PARTITION BY j.tenant_id, j.source_system, j.source_approval_id
            ORDER BY j.approver_employee_sk NULLS LAST, j._source_updated_at DESC NULLS LAST
        )                                            AS _grain_rn
    FROM joined j
)

SELECT
    leave_approval_sk,
    tenant_id,
    source_system,
    source_approval_id,
    leave_application_sk,
    applicant_employee_sk,
    approver_employee_sk,
    leave_approval_level_sk,
    approval_status_sk,
    action_date_sk,
    action_date,
    source_application_id,
    leave_source_code,
    source_approver_emp_id,
    approval_level_code,
    approval_level_name,
    approval_status_code,
    application_status_code,
    approval_sequence,
    approval_comment,
    is_final_approval,
    created_timestamp,
    updated_timestamp,
    _source_updated_at,
    _loaded_at
FROM final
WHERE _grain_rn = 1
