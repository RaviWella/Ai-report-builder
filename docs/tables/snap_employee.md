# snap_employee

## Overview

**Business Purpose:**  
dbt snapshot history for dim_employee (feeds warehouse SCD2 dimensions).

**Schema:** `hr_snap`  
**Object Type:** Table  
**Layer:** Snapshot  
**Domain:** Enterprise HR  
**Grain:** SCD2 snapshot — SCD2 employee version (conformed); superior_emp_no = immediate manager emp_no  
**Primary Key:** dbt_scd_id  
**Business Key:** employee_nk  
**SCD Type:** N/A  
**Refresh Type:** Batch  
**Refresh Frequency:** Daily  

**Source Systems:**
- TBD

**Consumers:**
- Semantic Views
- Reports
- AI Agent

## Governance

| Property | Value |
|----------|-------|
| Data Owner | HR Analytics |
| Technical Owner | Data Engineering |
| Classification | Internal |
| Contains PII | Yes |
| Retention | 7 years |

## Columns

| Column | Type | Nullable | Default | Description | Source | Transformation | PII | Sensitive | AI Aliases |
|--------|------|----------|---------|-------------|--------|----------------|-----|-----------|------------|
| `employee_nk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `tenant_id` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_system` | varchar(32) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_emp_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `emp_no` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | employee number, employee code, staff id |
| `epf_no` | varchar(64) | Yes | - | TBD | TBD | TBD | No | Yes | TBD |
| `emp_attendance_no` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `nic` | varchar(64) | Yes | - | TBD | TBD | TBD | Yes | No | TBD |
| `passport_no` | varchar(64) | Yes | - | TBD | TBD | TBD | Yes | No | TBD |
| `emp_title` | varchar(32) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `emp_fullname` | varchar(255) | Yes | - | TBD | TBD | TBD | No | No | employee name, full name, staff name |
| `emp_name` | varchar(255) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `emp_initial` | varchar(128) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `emp_finit` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `emp_surname` | varchar(128) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `gender` | varchar(32) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `date_of_birth` | date | Yes | - | TBD | TBD | TBD | Yes | No | TBD |
| `civil_status` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `residence` | varchar(255) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `nationality_name` | varchar(128) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `race_name` | varchar(128) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `religion_name` | varchar(128) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `work_email` | varchar(255) | Yes | - | TBD | TBD | TBD | Yes | No | TBD |
| `personal_email` | varchar(255) | Yes | - | TBD | TBD | TBD | Yes | No | TBD |
| `primary_mobile` | varchar(64) | Yes | - | TBD | TBD | TBD | Yes | No | TBD |
| `secondary_mobile` | varchar(64) | Yes | - | TBD | TBD | TBD | Yes | No | TBD |
| `office_phone` | varchar(64) | Yes | - | TBD | TBD | TBD | Yes | No | TBD |
| `office_extension` | varchar(32) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `home_phone` | varchar(64) | Yes | - | TBD | TBD | TBD | Yes | No | TBD |
| `legal_entity_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_desig_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `com_hierarchy_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `designation_name` | text | Yes | - | TBD | TBD | TBD | No | No | designation, job title, role |
| `designation_department` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `grade_name` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `employee_category` | varchar(128) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `employee_category_code` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `employment_type` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `employment_period` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `legal_entity_name` | varchar(255) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `legal_entity_code` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `location_name` | varchar(255) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `branch_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `branch_name` | varchar(255) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `branch_address` | varchar(512) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `emp_section_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `emp_position` | varchar(255) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `com_hierarchy_level` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `superior_emp_no` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `probation_status` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `emp_status` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `emp_lifecycle_status` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `basic_salary` | numeric(14,2) | Yes | - | TBD | TBD | TBD | No | Yes | TBD |
| `employee_carder` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `employee_carder_label` | varchar(255) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `employer_epf_pct` | numeric(6,2) | Yes | - | TBD | TBD | TBD | No | Yes | TBD |
| `employee_epf_pct` | numeric(6,2) | Yes | - | TBD | TBD | TBD | No | Yes | TBD |
| `is_day_salary` | boolean | Yes | - | TBD | TBD | TBD | No | Yes | TBD |
| `employee_group_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `shift_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `shift_group_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `attendance_group_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `holiday_calendar_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `leave_group_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `payroll_group` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `cost_center_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `classification_1_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `classification_2_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `classification_3_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `classification_4_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `join_date` | date | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `effective_date` | date | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `latest_probation_start_date` | date | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `probation_due_date` | date | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `probation_completed_date` | date | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `latest_contract_start_date` | date | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `employment_due_date` | date | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `resignation_given_date` | date | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `last_working_date` | date | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `resignation_effective_date` | date | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `last_resigned_date` | date | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `termination_effective_date` | date | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `deceased_effective_date` | date | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `vacate_effective_date` | date | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `interdict_effective_date` | date | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `retirement_date` | date | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_source_updated_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `dbt_scd_id` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `dbt_updated_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `dbt_valid_from` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `dbt_valid_to` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `superior_source_emp_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
