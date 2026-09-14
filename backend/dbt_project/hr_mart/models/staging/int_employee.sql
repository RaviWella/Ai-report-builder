-- int_employee — snapshot-ready employee row from MintHRM staging.
-- Maps stg_employees → Employment module column contract for snap_employee.

{{ config(materialized='view') }}

WITH hierarchy_individual_ranked AS (
    SELECT
        ref_emp_id,
        parent_id,
        ROW_NUMBER() OVER (
            PARTITION BY ref_emp_id
            ORDER BY updated_at DESC NULLS LAST, id DESC
        )                                                   AS rn
    FROM {{ source('hr_raw', 'stg_company_hierarchy_individual') }}
    WHERE ref_emp_id IS NOT NULL
),

hierarchy_individual AS (
    SELECT
        ref_emp_id                                          AS source_emp_id,
        NULLIF(parent_id, 0)                                AS superior_id
    FROM hierarchy_individual_ranked
    WHERE rn = 1
),

section_leader AS (
    SELECT
        id                                                  AS section_id,
        NULLIF(head_employee_id, 0)                         AS superior_id
    FROM {{ source('hr_raw', 'stg_departments') }}
    WHERE id IS NOT NULL
),

employee_lookup AS (
    SELECT
        id                                                  AS source_emp_id,
        NULLIF(TRIM(employee_code), '')                     AS emp_no
    FROM {{ source('hr_raw', 'stg_employees') }}
    WHERE id IS NOT NULL
),

staged AS (
    SELECT
        '{{ target.name }}'::varchar(64)                   AS tenant_id,
        '{{ var("source_system") }}'::varchar(32)           AS source_system,
        e.id                                              AS source_emp_id,
        e.employee_code                                   AS emp_no,
        e.epf_no,
        NULL::varchar(64)                                 AS emp_attendance_no,
        e.national_id                                     AS nic,
        NULL::varchar(64)                                 AS passport_no,

        NULL::varchar(32)                                 AS emp_title,
        COALESCE(e.full_name, e.first_name || ' ' || e.last_name)
                                                          AS emp_fullname,
        COALESCE(e.full_name, e.first_name || ' ' || e.last_name)
                                                          AS emp_name,
        e.first_name                                      AS emp_initial,
        NULL::varchar(64)                                 AS emp_finit,
        e.last_name                                       AS emp_surname,

        e.gender,
        e.date_of_birth,
        NULL::varchar(64)                                 AS civil_status,
        NULL::varchar(255)                                AS residence,
        NULL::varchar(128)                                AS nationality_name,
        NULL::varchar(128)                                AS race_name,
        NULL::varchar(128)                                AS religion_name,

        e.email                                           AS work_email,
        NULL::varchar(255)                                AS personal_email,
        e.phone                                           AS primary_mobile,
        NULL::varchar(64)                                 AS secondary_mobile,
        NULL::varchar(64)                                 AS office_phone,
        NULL::varchar(32)                                 AS office_extension,
        NULL::varchar(64)                                 AS home_phone,

        e.legal_entity_id,
        e.designation_id                                  AS source_desig_id,
        e.department_id                                   AS com_hierarchy_id,
        COALESCE(NULLIF(TRIM(e.designation_name), ''), d.title)
                                                          AS designation_name,
        NULLIF(TRIM(e.designation_department), '')        AS designation_department,
        e.grade_name,
        e.employee_category,
        e.employee_category_code,
        e.employment_type,
        NULL::varchar(64)                                 AS employment_period,
        e.legal_entity_name,
        e.legal_entity_code,
        e.location_name,
        e.branch_id,
        e.location_name                                   AS branch_name,
        NULL::varchar(512)                                AS branch_address,
        e.department_id                                   AS emp_section_id,
        NULL::varchar(255)                                AS emp_position,
        NULL::integer                                     AS com_hierarchy_level,
        COALESCE(
            hi.superior_id,
            NULLIF(e.reporting_to, 0),
            CASE
                WHEN sl.superior_id IS NOT NULL
                 AND sl.superior_id <> e.id
                THEN sl.superior_id
            END
        )                                                   AS resolved_superior_id,
        NULL::varchar(64)                                 AS probation_status,
        LOWER(COALESCE(e.employment_status, 'active'))    AS emp_status,
        LOWER(COALESCE(e.employment_status, 'active'))    AS emp_lifecycle_status,
        e.basic_salary,
        NULL::varchar(64)                                 AS employee_carder,
        NULL::varchar(255)                                AS employee_carder_label,
        NULL::numeric(6, 2)                               AS employer_epf_pct,
        NULL::numeric(6, 2)                               AS employee_epf_pct,
        NULL::boolean                                     AS is_day_salary,

        NULL::integer                                     AS employee_group_id,
        NULL::integer                                     AS shift_id,
        NULL::integer                                     AS shift_group_id,
        NULL::integer                                     AS attendance_group_id,
        NULL::integer                                     AS holiday_calendar_id,
        NULL::integer                                     AS leave_group_id,
        NULL::varchar(64)                                 AS payroll_group,
        e.cost_center_id,
        NULL::integer                                     AS classification_1_id,
        NULL::integer                                     AS classification_2_id,
        NULL::integer                                     AS classification_3_id,
        NULL::integer                                     AS classification_4_id,

        e.date_joined                                     AS join_date,
        e.date_joined                                     AS effective_date,
        NULL::date                                        AS latest_probation_start_date,
        NULL::date                                        AS probation_due_date,
        NULL::date                                        AS probation_completed_date,
        NULL::date                                        AS latest_contract_start_date,
        NULL::date                                        AS employment_due_date,
        NULL::date                                        AS resignation_given_date,
        NULL::date                                        AS last_working_date,
        e.date_resigned                                   AS resignation_effective_date,
        e.date_resigned                                   AS last_resigned_date,
        e.date_terminated                                 AS termination_effective_date,
        NULL::date                                        AS deceased_effective_date,
        NULL::date                                        AS vacate_effective_date,
        NULL::date                                        AS interdict_effective_date,
        NULL::date                                        AS retirement_date,

        COALESCE(e.updated_at, e.created_at, NOW())       AS _source_updated_at

    FROM {{ source('hr_raw', 'stg_employees') }} e
    LEFT JOIN {{ source('hr_raw', 'stg_designations') }} d
        ON d.id = e.designation_id
    LEFT JOIN hierarchy_individual hi
        ON hi.source_emp_id = e.id
    LEFT JOIN section_leader sl
        ON sl.section_id = e.department_id
    WHERE e.id IS NOT NULL
)

SELECT
    {{ dbt_utils.generate_surrogate_key(['s.tenant_id', 's.source_system', 's.source_emp_id']) }}
                                                      AS employee_nk,
    s.tenant_id,
    s.source_system,
    s.source_emp_id,
    s.emp_no,
    s.epf_no,
    s.emp_attendance_no,
    s.nic,
    s.passport_no,
    s.emp_title,
    s.emp_fullname,
    s.emp_name,
    s.emp_initial,
    s.emp_finit,
    s.emp_surname,
    s.gender,
    s.date_of_birth,
    s.civil_status,
    s.residence,
    s.nationality_name,
    s.race_name,
    s.religion_name,
    s.work_email,
    s.personal_email,
    s.primary_mobile,
    s.secondary_mobile,
    s.office_phone,
    s.office_extension,
    s.home_phone,
    s.legal_entity_id,
    s.source_desig_id,
    s.com_hierarchy_id,
    s.designation_name,
    s.designation_department,
    s.grade_name,
    s.employee_category,
    s.employee_category_code,
    s.employment_type,
    s.employment_period,
    s.legal_entity_name,
    s.legal_entity_code,
    s.location_name,
    s.branch_id,
    s.branch_name,
    s.branch_address,
    s.emp_section_id,
    s.emp_position,
    s.com_hierarchy_level,
    sup.emp_no                                        AS superior_emp_no,
    s.probation_status,
    s.emp_status,
    s.emp_lifecycle_status,
    s.basic_salary,
    s.employee_carder,
    s.employee_carder_label,
    s.employer_epf_pct,
    s.employee_epf_pct,
    s.is_day_salary,
    s.employee_group_id,
    s.shift_id,
    s.shift_group_id,
    s.attendance_group_id,
    s.holiday_calendar_id,
    s.leave_group_id,
    s.payroll_group,
    s.cost_center_id,
    s.classification_1_id,
    s.classification_2_id,
    s.classification_3_id,
    s.classification_4_id,
    s.join_date,
    s.effective_date,
    s.latest_probation_start_date,
    s.probation_due_date,
    s.probation_completed_date,
    s.latest_contract_start_date,
    s.employment_due_date,
    s.resignation_given_date,
    s.last_working_date,
    s.resignation_effective_date,
    s.last_resigned_date,
    s.termination_effective_date,
    s.deceased_effective_date,
    s.vacate_effective_date,
    s.interdict_effective_date,
    s.retirement_date,
    s._source_updated_at
FROM staged s
LEFT JOIN employee_lookup sup
    ON sup.source_emp_id = s.resolved_superior_id
