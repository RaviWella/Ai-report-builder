# mart_employee_current

## Overview

**Business Purpose:**  
Denormalized current-state OBT for active employees only. Computed age, tenure, probation flags. The thing BI dashboards point at.

**Schema:** `hr`  
**Object Type:** Table  
**Layer:** Mart  
**Domain:** Enterprise HR  
**Grain:** Current active employee OBT; resolves supervisor via superior_emp_no -> dim_employee.emp_no  
**Primary Key:** TBD  
**Business Key:** source_emp_id  
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
| `tenant_id` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `employee_sk` | text | Yes | - | FK to dim_employee.employee_sk. | TBD | TBD | No | No | TBD |
| `source_emp_id` | integer | Yes | - | Source PK; unique because mart filters to is_current AND emp_status='active'. | TBD | TBD | No | No | TBD |
| `emp_no` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | employee number, employee code, staff id |
| `epf_no` | varchar(64) | Yes | - | TBD | TBD | TBD | No | Yes | TBD |
| `emp_title` | varchar(32) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `emp_fullname` | varchar(255) | Yes | - | TBD | TBD | TBD | No | No | employee name, full name, staff name |
| `emp_name` | varchar(255) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `emp_initial` | varchar(128) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `emp_surname` | varchar(128) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `gender` | varchar(32) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `date_of_birth` | date | Yes | - | TBD | TBD | TBD | Yes | No | TBD |
| `age_years` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `civil_status` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `nationality` | varchar(128) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `nic` | varchar(64) | Yes | - | TBD | TBD | TBD | Yes | No | TBD |
| `passport_no` | varchar(64) | Yes | - | TBD | TBD | TBD | Yes | No | TBD |
| `designation` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `designation_department` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `grade` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `employee_category` | varchar(128) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `employee_category_code` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `employment_type` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `employment_period` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `employee_carder` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `employee_carder_label` | varchar(255) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `legal_entity` | varchar(255) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `legal_entity_code` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `location_name` | varchar(255) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `branch_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `emp_section_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `emp_position` | varchar(255) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `com_hierarchy_level` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `superior_emp_no` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `superior_fullname` | varchar(255) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `superior_designation` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `shift_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `shift_group_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `attendance_group_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `holiday_calendar_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `leave_group_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `payroll_group` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `cost_center_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `join_date` | date | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `tenure_years` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `tenure_bucket` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `latest_probation_start_date` | date | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `probation_due_date` | date | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `probation_completed_date` | date | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `probation_status` | varchar(255) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `is_on_probation` | boolean | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `is_probation_overdue` | boolean | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `latest_contract_start_date` | date | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `employment_due_date` | date | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `emp_status` | text | Yes | - | Should always be 'active' for this mart. | TBD | TBD | No | No | TBD |
| `emp_lifecycle_status` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `basic_salary` | numeric(14,2) | Yes | - | TBD | TBD | TBD | No | Yes | TBD |
| `_refreshed_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
