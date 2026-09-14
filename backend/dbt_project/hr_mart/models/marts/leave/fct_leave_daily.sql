-- =============================================================================
-- fct_leave_daily
-- Daily leave analytics — one row per employee per leave date (standard leave).
-- =============================================================================

{{ config(
    materialized='incremental',
    unique_key=['tenant_id', 'source_system', 'source_leave_date_id'],
    incremental_strategy='delete+insert',
    on_schema_change='sync_all_columns',
    tags=['leave', 'warehouse_marts'],
    indexes=[
        {'columns': ['tenant_id', 'employee_sk', 'leave_date'], 'unique': false},
        {'columns': ['tenant_id', 'date_sk'], 'unique': false},
        {'columns': ['tenant_id', 'leave_application_sk'], 'unique': false},
    ],
) }}

WITH daily AS (
    SELECT * FROM {{ ref('int_leave_daily') }}

    {% if is_incremental() %}
    WHERE _source_updated_at >= (
        SELECT COALESCE(MAX(_source_updated_at), '1970-01-01'::timestamptz) - INTERVAL '1 hour'
        FROM {{ this }}
    )
    {% endif %}
),

daily_norm AS (
    SELECT
        d.*,
        COALESCE(NULLIF(TRIM(d.source_system), ''), '{{ var("source_system") }}')
                                                    AS _source_system_norm
    FROM daily d
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

applications AS (
    SELECT
        leave_application_sk,
        tenant_id,
        source_system,
        source_application_id,
        leave_source_code
    FROM {{ ref('fct_leave_application') }}
),

joined AS (
    SELECT
        d.tenant_id,
        d._source_system_norm                        AS source_system,
        d.source_leave_date_id,
        d.source_application_id,
        d.leave_source_code,

        app.leave_application_sk,
        emp.employee_sk,
        lt.leave_type_sk,
        ls.leave_status_sk,
        dd.date_sk,
        TO_CHAR(d.leave_date, 'YYYYMMDD')::integer AS date_key,

        d.source_emp_id,
        d.source_leave_type_id,
        d.header_leave_status_code,
        d.leave_date,
        d.leave_day_count,
        (d.leave_day_count * 8.0)::numeric(8, 2)      AS leave_hours,
        CASE
            WHEN COALESCE(lt.is_paid_leave, TRUE) = FALSE
            THEN d.leave_day_count
            ELSE 0::numeric(8, 2)
        END                                          AS unpaid_leave_hours,

        d.is_half_day,
        d.half_day_type,
        d.coverup_approved,
        d.superior_approved,
        d.hr_approved,
        COALESCE(dd.is_weekend, FALSE)               AS is_weekend_overlap,
        FALSE                                        AS is_holiday_overlap,
        FALSE                                        AS attendance_adjustment_flag,

        d._source_updated_at,
        CURRENT_TIMESTAMP                            AS _loaded_at

    FROM daily_norm d

    LEFT JOIN {{ ref('dim_date') }} dd
        ON dd.calendar_date = d.leave_date

    LEFT JOIN applications app
        ON TRIM(app.tenant_id::text) = TRIM(d.tenant_id::text)
       AND app.source_system = d._source_system_norm
       AND app.source_application_id = d.source_application_id
       AND app.leave_source_code = d.leave_source_code

    LEFT JOIN LATERAL (
        SELECT e.employee_sk
        FROM employee e
        WHERE TRIM(e.tenant_id::text) = TRIM(d.tenant_id::text)
          AND e.source_system_norm = d._source_system_norm
          AND e.source_emp_id = d.source_emp_id
        ORDER BY
            CASE
                WHEN d.leave_date >= ((e.valid_from AT TIME ZONE 'UTC'))::date
                 AND d.leave_date < ((e.valid_to AT TIME ZONE 'UTC'))::date
                THEN 0 ELSE 1
            END,
            CASE WHEN e.is_current THEN 0 ELSE 1 END,
            e.valid_from DESC
        LIMIT 1
    ) emp ON TRUE

    LEFT JOIN LATERAL (
        SELECT t.leave_type_sk, t.is_paid_leave
        FROM leave_type t
        WHERE TRIM(t.tenant_id::text) = TRIM(d.tenant_id::text)
          AND t.source_system_norm = d._source_system_norm
          AND t.source_leave_type_id = d.source_leave_type_id
        ORDER BY
            CASE
                WHEN d.leave_date >= ((t.valid_from AT TIME ZONE 'UTC'))::date
                 AND d.leave_date < ((t.valid_to AT TIME ZONE 'UTC'))::date
                THEN 0 ELSE 1
            END,
            CASE WHEN t.is_current THEN 0 ELSE 1 END,
            t.valid_from DESC
        LIMIT 1
    ) lt ON TRUE

    LEFT JOIN leave_status ls
        ON ls.status_code = d.header_leave_status_code
),

final AS (
    SELECT
        j.*,
        {{ dbt_utils.generate_surrogate_key([
            'tenant_id', 'source_system', 'source_leave_date_id'
        ]) }}                                        AS leave_daily_sk,
        ROW_NUMBER() OVER (
            PARTITION BY j.tenant_id, j.source_system, j.source_leave_date_id
            ORDER BY j.employee_sk NULLS LAST, j._source_updated_at DESC NULLS LAST
        )                                            AS _grain_rn
    FROM joined j
)

SELECT
    leave_daily_sk,
    tenant_id,
    source_system,
    source_leave_date_id,
    leave_application_sk,
    employee_sk,
    leave_type_sk,
    leave_status_sk,
    date_sk,
    date_key,
    source_application_id,
    leave_source_code,
    source_emp_id,
    source_leave_type_id,
    header_leave_status_code,
    leave_date,
    leave_day_count,
    leave_hours,
    unpaid_leave_hours,
    is_half_day,
    half_day_type,
    coverup_approved,
    superior_approved,
    hr_approved,
    is_weekend_overlap,
    is_holiday_overlap,
    attendance_adjustment_flag,
    _source_updated_at,
    _loaded_at
FROM final
WHERE _grain_rn = 1
