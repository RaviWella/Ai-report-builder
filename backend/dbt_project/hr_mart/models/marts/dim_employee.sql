-- =============================================================================
-- dim_employee (mart)
-- Conformed employee dimension, SCD Type 2. Every fact in every module joins
-- here. Built on top of snap_employee, which does the actual SCD2 work via
-- dbt's native snapshot machinery.
--
-- What this model adds on top of the snapshot:
--   - Surrogate key (employee_sk) — stable per (emp, version)
--   - Renames dbt_valid_from/to → valid_from/to
--   - is_current boolean
--   - Integer version_number per employee
--   - BI spec §3.1 fields (contact, race, religion, branch, org hierarchy)
--   - dbt_scd_id lineage from snap_employee
-- =============================================================================

{{ config(
    materialized='table',
    indexes=[
      {'columns': ['tenant_id', 'source_emp_id'], 'unique': false},
      {'columns': ['tenant_id', 'emp_no'], 'unique': false},
      {'columns': ['tenant_id', 'emp_status'], 'unique': false},
      {'columns': ['tenant_id', 'legal_entity_name'], 'unique': false},
      {'columns': ['tenant_id', 'source_system', 'source_emp_id', 'valid_from'], 'unique': true}
    ]
) }}

with snap as (
    select
        *,
        dbt_valid_from                                        as valid_from,
        coalesce(dbt_valid_to, '9999-12-31 00:00:00+00'::timestamptz)
                                                              as valid_to,
        (dbt_valid_to is null)                                as is_current
    from {{ ref('snap_employee') }}
),

versioned as (
    select
        *,
        row_number() over (
            partition by tenant_id, source_system, source_emp_id
            order by valid_from
        )                                                     as version_number
    from snap
),

final as (
    select
        -- ============ SURROGATE KEY ============
        {{ dbt_utils.generate_surrogate_key([
            'v.tenant_id', 'v.source_system', 'v.source_emp_id', 'v.valid_from'
        ]) }}                                                 as employee_sk,

        v.dbt_scd_id,

        -- ============ NATURAL KEY ============
        v.tenant_id,
        v.source_system,
        v.source_emp_id,
        v.emp_no,
        v.epf_no,
        v.emp_attendance_no,
        v.nic,
        v.passport_no,

        -- ============ IDENTITY (Type 1) ============
        v.emp_title,
        v.emp_fullname,
        v.emp_name,
        v.emp_initial,
        v.emp_finit,
        v.emp_surname,

        -- ============ DEMOGRAPHICS (Type 1) ============
        v.gender,
        v.date_of_birth,
        v.civil_status,
        v.residence,
        v.nationality_name,
        v.race_name                                           as race,
        v.religion_name                                       as religion,

        -- ============ CONTACT (Type 1 — BI spec §3.1) ============
        v.work_email                                          as email,
        v.personal_email,
        v.primary_mobile                                      as mobile,
        v.secondary_mobile,
        v.office_phone,
        v.office_extension,
        v.home_phone,

        -- ============ EMPLOYMENT STRUCTURAL (Type 2 tracked in snapshot) ============
        v.legal_entity_id,
        v.source_desig_id,
        v.com_hierarchy_id,
        v.designation_name,
        v.designation_department,
        coalesce(ou.unit_name, v.designation_department)      as department_name,
        v.grade_name,
        v.employee_category,
        v.employee_category_code,
        v.employment_type,
        v.employment_period,
        v.legal_entity_name,
        v.legal_entity_code,
        v.location_name,
        v.branch_id,
        v.branch_name,
        v.branch_address,
        v.emp_section_id,
        v.emp_position,
        v.com_hierarchy_level,
        ou.level_2_name                                       as hierarchy_level_2,
        ou.level_3_name                                       as hierarchy_level_3,
        ou.level_4_name                                       as hierarchy_level_4,
        ou.org_unit_sk,
        v.superior_emp_no,
        v.probation_status::varchar                           as probation_status,
        v.emp_status,
        v.emp_lifecycle_status,
        v.basic_salary,
        v.employee_carder,
        v.employee_carder_label,
        v.employer_epf_pct,
        v.employee_epf_pct,
        v.is_day_salary,

        -- ============ EMPLOYMENT GROUP LINKAGES ============
        v.employee_group_id,
        v.shift_id,
        v.shift_group_id,
        v.attendance_group_id,
        v.holiday_calendar_id,
        v.leave_group_id,
        v.payroll_group,
        v.cost_center_id,
        v.classification_1_id,
        v.classification_2_id,
        v.classification_3_id,
        v.classification_4_id,

        -- ============ KEY DATES ============
        v.join_date,
        v.effective_date,
        v.latest_probation_start_date,
        v.probation_due_date,
        v.probation_completed_date,
        v.latest_contract_start_date,
        v.employment_due_date,
        v.resignation_given_date,
        v.last_working_date,
        v.resignation_effective_date,
        v.last_resigned_date,
        v.termination_effective_date,
        v.deceased_effective_date,
        v.vacate_effective_date,
        v.interdict_effective_date,
        v.retirement_date,

        -- ============ SCD2 COLUMNS ============
        v.valid_from,
        v.valid_to,
        v.is_current,
        v.version_number,

        -- ============ AUDIT ============
        v._source_updated_at,
        current_timestamp                                     as _loaded_at,

        -- ============ BACKWARD COMPAT (legacy facts / semantic views) ============
        v.source_emp_id                                       as employee_id,
        v.emp_section_id                                      as department_id,
        v.source_desig_id                                     as designation_id,
        v.emp_status                                          as employment_status,
        v.join_date                                           as date_joined,
        v.resignation_effective_date                          as date_resigned,
        v.termination_effective_date                          as date_terminated,
        (v.emp_status = 'active')                             as is_active

    from versioned v
    left join {{ ref('dim_org_unit') }} ou
        on  ou.tenant_id            = v.tenant_id
        and ou.source_system        = v.source_system
        and ou.source_hierarchy_id  = v.com_hierarchy_id
)

select * from final
