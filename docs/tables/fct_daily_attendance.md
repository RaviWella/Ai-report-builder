# fct_daily_attendance

## Overview

**Business Purpose:**  
Daily attendance fact (emp × shift_day × shift_order). Incremental delete+insert.

**Schema:** `hr`  
**Object Type:** Table  
**Layer:** Fact  
**Domain:** Attendance  
**Grain:** TBD  
**Primary Key:** daily_attendance_sk  
**Business Key:** source_atten_id, shift_order  
**SCD Type:** N/A  
**Refresh Type:** Batch  
**Refresh Frequency:** Daily  

**Source Systems:**
- HR_ATTEDANCE → stg_attendance

**Consumers:**
- Semantic Views
- Reports
- AI Agent

## Governance

| Property | Value |
|----------|-------|
| Data Owner | Workforce Analytics |
| Technical Owner | Data Engineering |
| Classification | Internal |
| Contains PII | No |
| Retention | 7 years |

## Columns

| Column | Type | Nullable | Default | Description | Source | Transformation | PII | Sensitive | AI Aliases |
|--------|------|----------|---------|-------------|--------|----------------|-----|-----------|------------|
| `tenant_id` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_system` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_atten_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `shift_order` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `employee_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `shift_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `planned_shift_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `date_key` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `shift_day_date_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `shift_day` | date | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `punch_in_datetime` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `punch_out_datetime` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `punch_in_two_datetime` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `punch_out_two_datetime` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `worked_seconds` | bigint | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `late_seconds` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `early_in_seconds` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `early_leave_seconds` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `overtime_seconds` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `worked_hours` | numeric(6,2) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `overtime_hours` | numeric(6,2) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `is_absent` | boolean | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `is_holiday` | boolean | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `holiday_name` | varchar(255) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `holiday_type` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `is_weekend` | boolean | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `worked_on_planned_shift` | boolean | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `has_overtime` | boolean | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `has_nopay` | boolean | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `late_status` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `early_leave_status` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `ot_status` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `is_attendance_processed` | boolean | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `is_salary_processed` | boolean | Yes | - | TBD | TBD | TBD | No | Yes | TBD |
| `is_approved` | boolean | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `is_manual_entry` | boolean | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `punch_in_location` | varchar(255) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `punch_out_location` | varchar(255) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `punch_in_latitude` | numeric(12,8) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `punch_in_longitude` | numeric(12,8) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `punch_out_latitude` | numeric(12,8) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `punch_out_longitude` | numeric(12,8) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `punch_in_branch` | varchar(128) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `punch_out_branch` | varchar(128) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `punch_in_requested_by` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `punch_out_requested_by` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `punch_in_approved_by` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `punch_out_approved_by` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `purpose` | varchar(255) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `note` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_source_updated_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_loaded_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
